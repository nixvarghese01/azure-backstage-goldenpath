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
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.10"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
}

# Creating app registrations needs Entra rights (Application Developer or the Graph permission
# Application.ReadWrite.OwnedBy). The first apply of this stack is done by a platform admin.
provider "azuread" {}

data "azurerm_client_config" "current" {}
data "azuread_client_config" "current" {}

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
  default = "azure-backstage-goldenpath"
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

variable "discovery_management_group_ids" {
  description = <<-EOT
    Management groups whose hierarchy the discovery identity may read, so the request form can show
    tenant -> management group -> subscription (Cloud Adoption Framework landing zones). Usually the
    intermediate root, e.g. ["xycorp"]. Empty = the form shows the Tenant Root Group only.
  EOT
  type        = list(string)
  default     = []
}

variable "state_storage_account_name" {
  type = string
}

variable "state_resource_group_name" {
  type = string
}

variable "key_vault_name" {
  type    = string
  default = "kv-idp-plat-dev"
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
  name     = "rg-idp-identities-${var.environment}"
  location = var.location
  tags     = local.tags
}

# ------------------------------------------------------------------ GitHub-federated identities
module "platform" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects = {
    "platform-apply" = "repo:${local.platform_repo}:environment:platform"
    # Destroy-only runs (platform-provision teardown, platform-ttl): no reviewers, so a forgotten
    # dev platform is always removed on time.
    "platform-teardown" = "repo:${local.platform_repo}:environment:platform-teardown"
  }
  tags = local.tags
}

module "platform_plan" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-plan-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-plan" = "repo:${local.platform_repo}:environment:platform-plan" }
  tags                = local.tags
}

module "platform_deploy" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-deploy-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-deploy" = "repo:${local.platform_repo}:environment:platform-deploy" }
  tags                = local.tags
}

module "vending" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-vending-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-vending" = "repo:${local.platform_repo}:environment:platform-vending" }
  tags                = local.tags
}

module "provisioning" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-provisioning-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "apps-plan" = local.app_subject.plan, "apps-apply" = local.app_subject.apply }
  tags                = local.tags
}

module "deployment" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-deployment-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "apps-build" = local.app_subject.build, "apps-deploy" = local.app_subject.deploy }
  tags                = local.tags
}

# ------------------------------------------------------------------ platform service identities
resource "azurerm_user_assigned_identity" "service" {
  for_each            = toset(["backstage", "discovery", "orchestrator"])
  name                = "id-idp-${each.key}-${var.environment}"
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

# Read-only view of the management group tree (no access to the resources inside it).
resource "azurerm_role_assignment" "discovery_management_group_reader" {
  for_each             = toset(var.discovery_management_group_ids)
  scope                = "/providers/Microsoft.Management/managementGroups/${each.value}"
  role_definition_name = "Management Group Reader"
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

# Secrets are NOT Terraform resources: managing azurerm_key_vault_secret would read real values back
# into state on every refresh. Instead (secret-management.md §6.1):
#   1. first apply creates the vault (secrets_created = false)
#   2. an operator creates the secrets with scripts/create-platform-secrets.sh (JIT Secrets Officer)
#   3. re-apply with secrets_created = true to grant each service access to ITS secrets only.
variable "secrets_created" {
  description = "Set to true once scripts/create-platform-secrets.sh has created the secrets."
  type        = bool
  default     = false
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

resource "azurerm_role_assignment" "secret_reader" {
  for_each             = var.secrets_created ? local.secrets : {}
  scope                = "${module.key_vault.id}/secrets/${each.key}"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.service[each.value].principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ platform identity scope
# The platform identity applies the shared stacks (20, 30): it is the most privileged identity and is
# only usable from platform-apply.yml behind the `platform` environment's required reviewers.
resource "azurerm_role_assignment" "platform" {
  for_each = {
    contributor = "Contributor"
    rbac        = "Role Based Access Control Administrator"
  }
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = each.value
  principal_id         = module.platform.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "platform_plan_reader" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = module.platform_plan.principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ Entra app registrations (token audiences)
# Service-to-service calls use Entra access tokens from workload identities. A token needs an audience,
# which must be an app registration exposing an identifier URI. v2 tokens: aud = the app's client ID.
resource "azuread_application" "audience" {
  for_each         = toset(["backstage", "discovery", "orchestrator"])
  display_name     = "idp-${each.key}-${var.environment}"
  identifier_uris  = ["api://idp-${each.key}-${var.environment}"]
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]

  api {
    requested_access_token_version = 2
  }
}

resource "azuread_service_principal" "audience" {
  for_each  = azuread_application.audience
  client_id = each.value.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

output "service_auth" {
  description = "Per service: the Entra audience to validate (aud) and the scope callers request."
  value = {
    for k, app in azuread_application.audience : k => {
      audience = app.client_id
      scope    = "api://idp-${k}-${var.environment}/.default"
    }
  }
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
