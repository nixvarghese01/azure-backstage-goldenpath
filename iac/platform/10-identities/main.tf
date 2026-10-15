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

variable "github_repo_id" {
  description = <<-EOT
    Numeric ID of the platform repository. With GitHub's immutable OIDC subjects
    (use_immutable_subject, the default for new repositories) the subject is
    repo:<owner>@<owner id>/<repo>@<repo id>:environment:<env>, which can't be claimed by a
    re-created repository with the same name. null = the older name-only subject.
  EOT
  type        = string
  default     = null
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
  # Subject prefix for the platform repository's own workflows (environment-bound).
  platform_subject = (var.github_repo_id == null
    ? "repo:${local.platform_repo}"
  : "repo:${var.github_org}@${var.github_org_id}/${var.platform_repo}@${var.github_repo_id}")
  reusable = "${var.github_org}/${var.platform_repo}/.github/workflows"
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

# Workload groups, one per function (CAF). Created here, empty, so the pipeline identities get rights
# inside them only and never on the whole subscription, which may hold other workloads. 20-shared-dev
# fills them; teardown empties them.
locals {
  workload_groups = {
    aks      = "platform"
    registry = "platform"
    data     = "platform"
    network  = "platform"
    apps     = "application"
  }
}

resource "azurerm_resource_group" "workload" {
  for_each = local.workload_groups
  name     = "rg-idp-${each.key}-${var.environment}"
  location = var.location
  tags     = merge(local.tags, { "lifecycle" = each.value })
}

# ------------------------------------------------------------------ GitHub-federated identities
module "platform" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects = {
    "platform-apply" = "${local.platform_subject}:environment:platform"
    # Destroy-only runs (platform-provision teardown, platform-ttl): no reviewers, so a forgotten
    # dev platform is always removed on time.
    "platform-teardown" = "${local.platform_subject}:environment:platform-teardown"
  }
  tags = local.tags
}

module "platform_plan" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-plan-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-plan" = "${local.platform_subject}:environment:platform-plan" }
  tags                = local.tags
}

module "platform_deploy" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-platform-deploy-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-deploy" = "${local.platform_subject}:environment:platform-deploy" }
  tags                = local.tags
}

module "vending" {
  source              = "../../modules/github-oidc-identity"
  name                = "id-idp-vending-${var.environment}"
  resource_group_name = azurerm_resource_group.identities.name
  location            = var.location
  subjects            = { "platform-vending" = "${local.platform_subject}:environment:platform-vending" }
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
  # postgres: the dev in-cluster database (deploy/charts/postgres) reads its passwords from Key Vault.
  for_each            = toset(["backstage", "discovery", "orchestrator", "postgres"])
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
  # Secret -> the workloads that may read it (per-secret RBAC). The database passwords are read by the
  # service and by postgres, which creates the login roles (dev in-cluster PostgreSQL only).
  secrets = {
    "gh-app-backstage-key"               = ["backstage"]
    "gh-app-backstage-client-secret"     = ["backstage"]
    "backstage-session-secret"           = ["backstage"]
    "gh-app-orchestrator-key"            = ["orchestrator"]
    "gh-app-orchestrator-webhook-secret" = ["orchestrator"]
    "postgres-password"                  = ["postgres"]
    "backstage-db-password"              = ["backstage", "postgres"]
    "orchestrator-db-password"           = ["orchestrator", "postgres"]
  }
  secret_grants = merge([
    for secret, readers in local.secrets : { for r in readers : "${secret}/${r}" => { secret = secret, reader = r } }
  ]...)
}

resource "azurerm_role_assignment" "secret_reader" {
  for_each             = var.secrets_created ? local.secret_grants : {}
  scope                = "${module.key_vault.id}/secrets/${each.value.secret}"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.service[each.value.reader].principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ platform identity scope
# The platform identity applies the shared stacks (20, 30): it is the most privileged identity and is
# only usable from platform-apply.yml behind the `platform` environment's required reviewers.
resource "azurerm_role_assignment" "platform" {
  for_each = {
    for pair in setproduct(keys(local.workload_groups), ["Contributor", "Role Based Access Control Administrator"]) :
    "${pair[0]}-${pair[1] == "Contributor" ? "contributor" : "rbac"}" => { group = pair[0], role = pair[1] }
  }
  scope                = azurerm_resource_group.workload[each.value.group].id
  role_definition_name = each.value.role
  principal_id         = module.platform.principal_id
  principal_type       = "ServicePrincipal"
}

# Reads outside its groups (identities, the subscription's capabilities); no write anywhere else.
resource "azurerm_role_assignment" "platform_reader" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = module.platform.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "platform_plan_reader" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = module.platform_plan.principal_id
  principal_type       = "ServicePrincipal"
}

# ------------------------------------------------------------------ provisioning identity scope
# Applied by an admin with this stack (creating a role definition needs roleDefinitions/write, which
# the pipeline identities don't have). Generated repositories use these rights through
# reusable-terraform.yml: a narrow custom role, and RBAC Administrator limited by ABAC to three roles.
locals {
  # Roles the provisioning identity may hand out (ABAC condition on RBAC Administrator).
  assignable_role_ids = [
    "ba92f5b4-2d11-453d-a403-e96b0029c9fe", # Storage Blob Data Contributor
    "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1", # Storage Blob Data Reader
    "4633458b-17de-408a-b874-0445c86b69e6", # Key Vault Secrets User
  ]
  rbac_condition = <<-EOT
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})
     )
     OR
     (
      @Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${join(", ", local.assignable_role_ids)}}
     )
    )
    AND
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})
     )
     OR
     (
      @Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${join(", ", local.assignable_role_ids)}}
     )
    )
  EOT
}

# Narrow custom role for application infrastructure (create-new RG, identities, storage, key vault).
resource "azurerm_role_definition" "app_provisioner" {
  name        = "IDP App Provisioner (${var.environment})"
  scope       = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  description = "Creates application infrastructure for the IDP golden path. No compute, network or RBAC beyond the conditioned assignment role."
  permissions {
    actions = [
      "*/read",
      "Microsoft.Resources/subscriptions/resourceGroups/write",
      "Microsoft.Resources/subscriptions/resourceGroups/delete",
      "Microsoft.Resources/deployments/*",
      "Microsoft.ManagedIdentity/userAssignedIdentities/*",
      "Microsoft.Storage/storageAccounts/*",
      "Microsoft.KeyVault/vaults/*",
      "Microsoft.ContainerService/managedClusters/listClusterUserCredential/action",
    ]
    not_actions = [
      "Microsoft.Storage/storageAccounts/listKeys/action",
      "Microsoft.Storage/storageAccounts/regenerateKey/action",
    ]
  }
  assignable_scopes = ["/subscriptions/${data.azurerm_client_config.current.subscription_id}"]
}

# Applications land in the approved apps group: on a shared subscription the golden path can't
# create resource groups or touch anything outside rg-idp-apps-<env>.
resource "azurerm_role_assignment" "provisioning_app_provisioner" {
  scope              = azurerm_resource_group.workload["apps"].id
  role_definition_id = azurerm_role_definition.app_provisioner.role_definition_resource_id
  principal_id       = module.provisioning.principal_id
  principal_type     = "ServicePrincipal"
}

resource "azurerm_role_assignment" "provisioning_rbac_admin" {
  scope                = azurerm_resource_group.workload["apps"].id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = module.provisioning.principal_id
  principal_type       = "ServicePrincipal"
  condition_version    = "2.0"
  condition            = local.rbac_condition
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

# ------------------------------------------------------------------ Workload Identity federation
# 30-cluster-config links the platform services' identities to their Kubernetes service accounts. That
# needs the cluster's OIDC issuer (known only after 20-shared-dev), so the platform identity creates
# those federated credentials, and may do only that, only on these three identities.
resource "azurerm_role_definition" "workload_identity_federation" {
  name        = "IDP Workload Identity Federation (${var.environment})"
  scope       = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  description = "Manage federated credentials on a user-assigned identity; nothing else."
  permissions {
    actions = [
      "Microsoft.ManagedIdentity/userAssignedIdentities/read",
      "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/read",
      "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write",
      "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/delete",
    ]
  }
  assignable_scopes = ["/subscriptions/${data.azurerm_client_config.current.subscription_id}"]
}

resource "azurerm_role_assignment" "platform_workload_identity_federation" {
  for_each           = azurerm_user_assigned_identity.service
  scope              = each.value.id
  role_definition_id = azurerm_role_definition.workload_identity_federation.role_definition_resource_id
  principal_id       = module.platform.principal_id
  principal_type     = "ServicePrincipal"
}

# ------------------------------------------------------------------ AKS admin group for automation
# The clusters use Kubernetes RBAC with Entra ID: cluster-admin comes only from the groups in
# admin_group_object_ids (20-shared-dev). The platform identity applies 30-cluster-config (namespaces,
# Gateway, RBAC), so it is the only member of this group. Humans use their own break-glass group.
resource "azuread_group" "aks_platform_admins" {
  display_name     = "idp-aks-platform-${var.environment}"
  description      = "Cluster-admin on the IDP's AKS clusters for the platform pipeline identity only."
  security_enabled = true
  owners           = [data.azuread_client_config.current.object_id]
  members          = [module.platform.principal_id]
}

output "aks_platform_admin_group_id" {
  description = "Add to admin_group_object_ids in 20-shared-dev."
  value       = azuread_group.aks_platform_admins.object_id
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
    postgres        = azurerm_user_assigned_identity.service["postgres"].client_id
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

output "resource_groups" {
  description = "Workload resource groups the pipelines may change."
  value       = { for k, g in azurerm_resource_group.workload : k => g.name }
}

output "key_vault_name" {
  value = module.key_vault.name
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}
