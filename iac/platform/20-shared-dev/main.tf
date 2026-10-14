# Shared dev platform: resource groups, AKS (+ clusters.d), ACR (+ registries.d), PostgreSQL, DNS,
# shared demo storage, and the role assignments the app/deploy identities need. Sized for a free
# subscription by default (docs/operations/demo-environment.md).

terraform {
  required_version = "~> 1.16.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.13"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
}

provider "azapi" {}

data "azurerm_client_config" "current" {}

variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "uksouth"
}

variable "admin_group_object_ids" {
  description = "Entra groups with cluster-admin (platform team / break-glass)."
  type        = list(string)
}

variable "aks" {
  type = object({
    name     = string
    sku_tier = optional(string, "Free")
    system_pool = optional(object({ vm_size = string, node_count = number, zones = optional(list(string), []),
      os_disk_size_gb = optional(number) }),
    { vm_size = "Standard_D2s_v5", node_count = 1 })
    user_pool = optional(object({ vm_size = string, node_count = number, zones = list(string) }), null)
  })
  default = { name = "aks-idp-shared-dev" }
}

variable "acr" {
  type = object({
    name = string
    sku  = optional(string, "Basic")
  })
  default = { name = "acridpdev" }
}

variable "postgres_name" {
  type    = string
  default = "psql-idp-dev"
}

variable "postgres_allowed_ips" {
  type    = map(string)
  default = {}
}

variable "dns_zone_name" {
  description = "Optional public DNS zone for application endpoints. null = none (the demo uses dev.xycorp.local through hosts entries or private DNS)."
  type        = string
  default     = null
  validation {
    # .local is reserved for multicast DNS (RFC 6762) and can't be served from a public zone.
    condition     = var.dns_zone_name == null || !endswith(coalesce(var.dns_zone_name, "x"), ".local")
    error_message = "A public DNS zone can't serve .local names; use an Azure Private DNS zone or hosts entries instead."
  }
}

variable "shared_storage_name" {
  description = "Shared demo storage account that apps can reuse (Select existing)."
  type        = string
  default     = "stidpshareddev"
}

variable "identity_resource_group" {
  type    = string
  default = "rg-idp-identities-dev"
}

variable "tags" {
  description = "Extra or overriding tags, e.g. the organisation tags a landing zone policy requires."
  type        = map(string)
  default     = {}
}

locals {
  # CAF tagging. var.tags adds or overrides organisation tags (costCenter, criticality, ...); the
  # landing zone may require some of them on resource groups.
  tags = merge({
    "managed-by"         = "idp-platform"
    "workload"           = "idp"
    "environment"        = var.environment
    "lifecycle"          = "platform"
    "application"        = "idp-platform"
    "owner"              = "platform-team"
    "costCenter"         = "platform"
    "criticality"        = "low"
    "dataClassification" = "internal"
  }, var.tags)
  extra_clusters = {
    for f in fileset(path.module, "clusters.d/*.json") :
    trimsuffix(basename(f), ".json") => jsondecode(file("${path.module}/${f}"))
  }
  extra_registries = {
    for f in fileset(path.module, "registries.d/*.json") :
    trimsuffix(basename(f), ".json") => jsondecode(file("${path.module}/${f}"))
  }
}

# ------------------------------------------------------------------ identities from 10-identities
data "azurerm_user_assigned_identity" "id" {
  for_each            = toset(["platform", "platform-deploy", "provisioning", "deployment", "backstage", "orchestrator"])
  name                = "id-idp-${each.key}-${var.environment}"
  resource_group_name = var.identity_resource_group
}

# ------------------------------------------------------------------ resource groups
resource "azurerm_resource_group" "platform" {
  name     = "rg-idp-platform-${var.environment}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_resource_group" "apps" {
  name     = "rg-idp-apps-${var.environment}"
  location = var.location
  tags     = merge(local.tags, { "lifecycle" = "application" })
}

# ------------------------------------------------------------------ AKS
module "aks" {
  source                 = "../../modules/aks-cluster"
  name                   = var.aks.name
  resource_group_name    = azurerm_resource_group.platform.name
  location               = var.location
  sku_tier               = var.aks.sku_tier
  tenant_id              = data.azurerm_client_config.current.tenant_id
  admin_group_object_ids = var.admin_group_object_ids
  system_pool            = var.aks.system_pool
  user_pool              = var.aks.user_pool
  tags                   = local.tags
}

module "extra_aks" {
  for_each               = local.extra_clusters
  source                 = "../../modules/aks-cluster"
  name                   = each.key
  resource_group_name    = azurerm_resource_group.platform.name
  location               = try(each.value.location, var.location)
  sku_tier               = try(each.value.zonal, false) ? "Standard" : "Free"
  tenant_id              = data.azurerm_client_config.current.tenant_id
  admin_group_object_ids = var.admin_group_object_ids
  user_pool = try(each.value.zonal, false) ? {
    vm_size = "Standard_D2s_v5", node_count = 3, zones = ["1", "2", "3"]
  } : null
  tags = merge(local.tags, { "request-id" = try(each.value.request_id, "") })
}

locals {
  clusters = merge({ (var.aks.name) = module.aks }, module.extra_aks)
}

# ------------------------------------------------------------------ ACR
module "acr" {
  source              = "../../modules/container-registry"
  name                = var.acr.name
  resource_group_name = azurerm_resource_group.platform.name
  location            = var.location
  sku                 = var.acr.sku
  tags                = local.tags
}

module "extra_acr" {
  for_each            = local.extra_registries
  source              = "../../modules/container-registry"
  name                = each.key
  resource_group_name = azurerm_resource_group.platform.name
  location            = try(each.value.location, var.location)
  tags                = merge(local.tags, { "request-id" = try(each.value.request_id, "") })
}

locals {
  registries = merge({ (var.acr.name) = module.acr }, module.extra_acr)
}

# ------------------------------------------------------------------ PostgreSQL (platform state)
module "postgres" {
  source              = "../../modules/postgresql-flexible"
  name                = var.postgres_name
  resource_group_name = azurerm_resource_group.platform.name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  allowed_ips         = var.postgres_allowed_ips
  entra_admin = {
    object_id      = data.azurerm_user_assigned_identity.id["platform"].principal_id
    principal_name = data.azurerm_user_assigned_identity.id["platform"].name
    principal_type = "ServicePrincipal"
  }
  tags = local.tags
}

# ------------------------------------------------------------------ DNS (optional)
resource "azurerm_dns_zone" "apps" {
  count               = var.dns_zone_name == null ? 0 : 1
  name                = var.dns_zone_name
  resource_group_name = azurerm_resource_group.platform.name
  tags                = local.tags
}

# ------------------------------------------------------------------ shared demo storage (reusable)
module "shared_storage" {
  source              = "../../modules/storage-account"
  name                = var.shared_storage_name
  resource_group_name = azurerm_resource_group.apps.name
  location            = var.location
  containers          = ["shared"]
  tags                = merge(local.tags, { "lifecycle" = "application", "application" = "shared" })
}

# ------------------------------------------------------------------ role assignments
# The provisioning identity's custom role and subscription-level assignments live in 10-identities:
# creating a role definition needs Microsoft.Authorization/roleDefinitions/write, which the pipeline's
# platform identity (Contributor + RBAC Administrator) deliberately doesn't have.

resource "azurerm_role_assignment" "acr_pull" {
  for_each             = { for k, c in local.clusters : k => c }
  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = each.value.kubelet_object_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "acr_push" {
  for_each = {
    for pair in setproduct(keys(local.registries), ["deployment", "platform-deploy"]) :
    "${pair[0]}/${pair[1]}" => { acr = pair[0], id = pair[1] }
  }
  scope                = local.registries[each.value.acr].id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_user_assigned_identity.id[each.value.id].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "aks_user" {
  for_each = {
    for pair in setproduct(keys(local.clusters), ["provisioning", "deployment", "platform-deploy"]) :
    "${pair[0]}/${pair[1]}" => { cluster = pair[0], id = pair[1] }
  }
  scope                = local.clusters[each.value.cluster].id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = data.azurerm_user_assigned_identity.id[each.value.id].principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ outputs
output "aks" {
  value = { for k, c in local.clusters : k => { id = c.id, oidc_issuer_url = c.oidc_issuer_url, host = c.host } }
}

output "acr_login_servers" {
  value = { for k, r in local.registries : k => r.login_server }
}

output "postgres_fqdn" {
  value = module.postgres.fqdn
}

output "dns_zone_name_servers" {
  value = var.dns_zone_name == null ? [] : azurerm_dns_zone.apps[0].name_servers
}
