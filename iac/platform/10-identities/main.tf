# Platform identities and their trust (README "Identity and security model", secret-management.md).
#
# GitHub OIDC subjects:
#  * platform repo workflows: the default subject  repo:<org>/<repo>:environment:<env>
#  * generated repos: one credential per environment that trusts ONLY the platform's reviewed reusable
#    workflow, using the org's customised subject claim (ADR-0005):
#      repository_owner_id:<id>:environment:<env>:job_workflow_ref:<org>/<repo>/.github/workflows/<wf>@<ref>
#
# Kubernetes Workload Identity federation for the platform services lives in 30-cluster-config,
# because it needs the cluster's OIDC issuer.

terraform {
  required_version = "~> 1.16.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
}

data "azurerm_client_config" "current" {}

variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "uksouth"
}

variable "github_org" {
  type = string
}

variable "github_org_id" {
  description = "Numeric GitHub organisation ID (used in the customised OIDC subject)."
  type        = string
}

variable "platform_repo" {
  type    = string
  default = "sportify-azure-backstage"
}

variable "reusable_workflow_ref" {
  description = "Git ref the generated repos pin the reusable workflows to."
  type        = string
  default     = "refs/heads/main"
}

variable "discovery_subscription_ids" {
  description = "Allowlisted subscriptions the discovery identity may read."
  type        = list(string)
}

variable "state_storage_account_name" {
  type = string
}

variable "state_resource_group_name" {
  type = string
}

variable "key_vault_name" {
  type    = string
  default = "kv-sportify-plat-dev"
}

locals {
  tags = {
    "managed-by"  = "sportify-platform"
    "environment" = var.environment
    "lifecycle"   = "platform"
    "application" = "sportify-platform"
    "owner"       = "platform-team"
  }
  platform_repo = "${var.github_org}/${var.platform_repo}"
  reusable      = "${var.github_org}/${var.platform_repo}/.github/workflows"
  app_subject = {
    for k, v in {
      plan   = { env = "${var.environment}-infra-plan", wf = "reusable-terraform.yml" }
      apply  = { env = "${var.environment}-infra", wf = "reusable-terraform.yml" }
      build  = { env = "${var.environment}-build", wf = "reusable-application-ci.yml" }
      deploy = { env = var.environment, wf = "reusable-application-deploy.yml" }
    } : k => "repository_owner_id:${var.github_org_id}:environment:${v.env}:job_workflow_ref:${local.reusable}/${v.wf}@${var.reusable_workflow_ref}"
  }
}

resource "azurerm_resource_group" "identities" {
  name     = "rg-sportify-identities-${var.environment}"
  location = var.location
  tags     = local.tags
}

# ------------------------------------------------------------------ GitHub-federated identities
module "platform" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-platform-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-apply" = "repo:${local.platform_repo}:environment:platform" }
  tags                = local.tags
}

module "platform_plan" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-platform-plan-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-plan" = "repo:${local.platform_repo}:environment:platform-plan" }
  tags                = local.tags
}

module "platform_deploy" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-platform-deploy-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-deploy" = "repo:${local.platform_repo}:environment:platform-deploy" }
  tags                = local.tags
}

module "vending" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-vending-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-vending" = "repo:${local.platform_repo}:environment:platform-vending" }
  tags                = local.tags
}

module "provisioning" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-provisioning-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "apps-plan" = local.app_subject.plan, "apps-apply" = local.app_subject.apply }
  tags                = local.tags
}

module "deployment" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-sportify-deployment-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "apps-build" = local.app_subject.build, "apps-deploy" = local.app_subject.deploy }
  tags                = local.tags
}

# ------------------------------------------------------------------ platform service identities
resource "azurerm_user_assigned_identity" "service" {
  for_each            = toset(["backstage", "discovery", "orchestrator"])
  name                = "id-sportify-${each.key}-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "discovery_reader" {
  for_each             = toset(var.discovery_subscription_ids)
  scope                = "/subscriptions/${each.value}"
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.service["discovery"].principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ Terraform state access
data "azurerm_storage_account" "state" {
  name                = var.state_storage_account_name
  resource_group_name = var.state_resource_group_name
}

locals {
  state_containers = { for c in ["platform", "apps"] : c => "${data.azurerm_storage_account.state.id}/blobServices/default/containers/${c}" }
}

resource "azurerm_role_assignment" "state" {
  for_each = {
    platform_rw = { scope = local.state_containers.platform, role = "Storage Blob Data Contributor", p = module.platform.principal_id }
    plan_ro     = { scope = local.state_containers.platform, role = "Storage Blob Data Reader", p = module.platform_plan.principal_id }
    vending_rw  = { scope = local.state_containers.platform, role = "Storage Blob Data Contributor", p = module.vending.principal_id }
    apps_rw     = { scope = local.state_containers.apps, role = "Storage Blob Data Contributor", p = module.provisioning.principal_id }
  }
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = each.value.p
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ platform Key Vault, per-secret RBAC
module "key_vault" {
  source              = "../../modules/key-vault"
  name                = var.key_vault_name
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = local.tags
}

# The platform identity creates the secret *names* (placeholders) so access can be granted per secret.
# Real values are set out of band (secret-management.md §6.1); Terraform ignores value changes, so
# real values never enter state or plans.
resource "azurerm_role_assignment" "platform_secrets_officer" {
  scope                = module.key_vault.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = module.platform.principal_id
  principal_type       = "ServicePrincipal"
}

locals {
  secrets = {
    "gh-app-backstage-key"               = "backstage"
    "gh-app-backstage-client-secret"     = "backstage"
    "backstage-session-secret"           = "backstage"
    "gh-app-orchestrator-key"            = "orchestrator"
    "gh-app-orchestrator-webhook-secret" = "orchestrator"
  }
}

resource "azurerm_key_vault_secret" "placeholder" {
  for_each     = local.secrets
  name         = each.key
  value        = "set-out-of-band"
  key_vault_id = module.key_vault.id
  content_type = "set-out-of-band"
  tags         = { owner = "platform-team", "rotation-days" = each.key == "backstage-session-secret" ? "180" : "90" }

  lifecycle {
    ignore_changes = [value, content_type, expiration_date, tags]
  }
  depends_on = [azurerm_role_assignment.platform_secrets_officer]
}

resource "azurerm_role_assignment" "secret_reader" {
  for_each             = local.secrets
  scope                = azurerm_key_vault_secret.placeholder[each.key].resource_versionless_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.service[each.value].principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ outputs (IDs only, no secrets)
output "client_ids" {
  description = "Set these as GitHub Actions *variables* (not secrets)."
  value = {
    platform        = module.platform.client_id
    platform_plan   = module.platform_plan.client_id
    platform_deploy = module.platform_deploy.client_id
    vending         = module.vending.client_id
    provisioning    = module.provisioning.client_id
    deployment      = module.deployment.client_id
    backstage       = azurerm_user_assigned_identity.service["backstage"].client_id
    discovery       = azurerm_user_assigned_identity.service["discovery"].client_id
    orchestrator    = azurerm_user_assigned_identity.service["orchestrator"].client_id
  }
}

output "principal_ids" {
  value = {
    platform        = module.platform.principal_id
    platform_deploy = module.platform_deploy.principal_id
    provisioning    = module.provisioning.principal_id
    deployment      = module.deployment.principal_id
    backstage       = azurerm_user_assigned_identity.service["backstage"].principal_id
    discovery       = azurerm_user_assigned_identity.service["discovery"].principal_id
    orchestrator    = azurerm_user_assigned_identity.service["orchestrator"].principal_id
  }
}

output "key_vault_name" {
  value = module.key_vault.name
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}
