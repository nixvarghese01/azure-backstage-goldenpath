# Standard application root module. Identical in every generated repository; only tfvars differ.
# "Create new" resources come from versioned platform modules; "Select existing" resources are read
# with data sources and never modified or destroyed - the platform only adds role assignments.

module "naming" {
  source            = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/naming?ref=naming/v1.0.0"
  application       = var.application
  environment       = var.environment
  owner             = var.owner
  request_id        = var.request_id
  repository        = var.repository
  availability_tier = var.availability_tier
}

# ------------------------------------------------------------------ resource group
module "resource_group" {
  count    = var.resource_group.mode == "new" ? 1 : 0
  source   = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/resource-group?ref=resource-group/v1.0.0"
  name     = var.resource_group.name
  location = var.region
  tags     = module.naming.tags
}

data "azurerm_resource_group" "existing" {
  count = var.resource_group.mode == "existing" ? 1 : 0
  name  = var.resource_group.name
}

locals {
  rg_name     = var.resource_group.mode == "new" ? module.resource_group[0].name : data.azurerm_resource_group.existing[0].name
  rg_location = var.resource_group.mode == "new" ? module.resource_group[0].location : data.azurerm_resource_group.existing[0].location
}

# ------------------------------------------------------------------ shared platform resources (read only)
data "azurerm_container_registry" "shared" {
  name                = var.container_registry.name
  resource_group_name = var.container_registry.resource_group
}

data "azurerm_user_assigned_identity" "deployer" {
  name                = var.deployment_identity.name
  resource_group_name = var.deployment_identity.resource_group
}

# ------------------------------------------------------------------ runtime identity (Workload Identity)
module "runtime_identity" {
  source              = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/app-identity?ref=app-identity/v1.0.0"
  name                = module.naming.names.runtime_identity
  resource_group_name = local.rg_name
  location            = local.rg_location
  oidc_issuer_url     = data.azurerm_kubernetes_cluster.target.oidc_issuer_url
  namespace           = var.namespace.name
  service_account     = module.naming.names.service_account
  tags                = module.naming.tags
}

# ------------------------------------------------------------------ namespace
module "namespace" {
  count                 = var.namespace.mode == "new" ? 1 : 0
  source                = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/app-namespace?ref=app-namespace/v1.0.0"
  name                  = var.namespace.name
  owner                 = var.owner
  deployer_principal_id = data.azurerm_user_assigned_identity.deployer.principal_id
  availability_tier     = var.availability_tier
}

data "kubernetes_namespace_v1" "existing" {
  count = var.namespace.mode == "existing" ? 1 : 0
  metadata {
    name = var.namespace.name
  }
}

check "existing_namespace_owned_by_team" {
  assert {
    condition = var.namespace.mode == "new" || try(
      data.kubernetes_namespace_v1.existing[0].metadata[0].labels["sportify.io/owner"], ""
    ) == var.owner
    error_message = "The existing namespace is not labelled as owned by ${var.owner}."
  }
}

# ------------------------------------------------------------------ runtime capability: Storage
module "storage" {
  count               = var.runtime_capability.type == "storage" && var.runtime_capability.mode == "new" ? 1 : 0
  source              = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/storage-account?ref=storage-account/v1.0.0"
  name                = var.runtime_capability.name
  resource_group_name = local.rg_name
  location            = local.rg_location
  availability_tier   = var.availability_tier
  tags                = module.naming.tags
}

data "azurerm_storage_account" "existing" {
  count               = var.runtime_capability.type == "storage" && var.runtime_capability.mode == "existing" ? 1 : 0
  name                = var.runtime_capability.name
  resource_group_name = coalesce(var.runtime_capability.resource_group, local.rg_name)
}

# ------------------------------------------------------------------ runtime capability: Key Vault
data "azurerm_client_config" "current" {}

module "key_vault" {
  count               = var.runtime_capability.type == "keyvault" && var.runtime_capability.mode == "new" ? 1 : 0
  source              = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/key-vault?ref=key-vault/v1.0.0"
  name                = var.runtime_capability.name
  resource_group_name = local.rg_name
  location            = local.rg_location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = module.naming.tags
}

data "azurerm_key_vault" "existing" {
  count               = var.runtime_capability.type == "keyvault" && var.runtime_capability.mode == "existing" ? 1 : 0
  name                = var.runtime_capability.name
  resource_group_name = coalesce(var.runtime_capability.resource_group, local.rg_name)
}

locals {
  storage_id   = try(module.storage[0].id, data.azurerm_storage_account.existing[0].id, null)
  storage_name = try(module.storage[0].name, data.azurerm_storage_account.existing[0].name, null)
  vault_id     = try(module.key_vault[0].id, data.azurerm_key_vault.existing[0].id, null)
  vault_uri    = try(module.key_vault[0].uri, data.azurerm_key_vault.existing[0].vault_uri, null)

  capability_scope = var.runtime_capability.type == "storage" ? local.storage_id : local.vault_id
  capability_role  = var.runtime_capability.type == "storage" ? "Storage Blob Data Contributor" : "Key Vault Secrets User"
}

# ------------------------------------------------------------------ least-privilege access for the app
module "runtime_access" {
  count                = var.runtime_capability.type == "none" ? 0 : 1
  source               = "git::https://github.com/sportify-org/sportify-azure-backstage.git//iac/modules/role-assignment?ref=role-assignment/v1.0.0"
  scope                = local.capability_scope
  role_definition_name = local.capability_role
  principal_id         = module.runtime_identity.principal_id
}
