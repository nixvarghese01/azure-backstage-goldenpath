# In-cluster platform configuration for an EXISTING cluster (never created in the same config):
# namespaces, the shared Gateway (ADR-0003) with its public TLS certificate (cert-manager, Let's Encrypt,
# kept in Key Vault), ClusterRoles/bindings for the provisioning and deployment identities
# (ADR-0002 §9), and Workload Identity federation for the platform services.

terraform {
  required_version = "~> 1.16.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.3"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.3"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "cluster_name" {
  type    = string
  default = "aks-idp-shared-dev"
}

variable "cluster_resource_group" {
  type    = string
  default = "rg-idp-aks-dev"
}

variable "identity_resource_group" {
  type    = string
  default = "rg-idp-identities-dev"
}

variable "kubelogin_mode" {
  description = "azurecli locally, workloadidentity in GitHub Actions (platform-apply)."
  type        = string
  default     = "azurecli"
}

variable "gateway_hostname" {
  description = "Wildcard listener hostname, e.g. *.dev.xycorp.local. null = accept any host."
  type        = string
  default     = null
}

variable "public_dns_label" {
  description = "Azure DNS label on the Gateway's public IP: <label>.<region>.cloudapp.azure.com, unique per region. The name stays when the IP changes (each provision), so the GitHub App URLs don't. null = idp-<environment>-<hash of the cluster ID>."
  type        = string
  default     = null
}

variable "public_tls" {
  description = "Let's Encrypt certificate for the public host (cert-manager) and an HTTPS listener. false = HTTP only."
  type        = bool
  default     = true
}

variable "acme_email" {
  description = "Optional e-mail for Let's Encrypt expiry notices."
  type        = string
  default     = ""
}

variable "gateway_tls_secret" {
  description = "An own TLS Secret for the HTTPS listener instead of the Let's Encrypt one (public_tls)."
  type        = string
  default     = null
}

data "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  resource_group_name = var.cluster_resource_group
}

provider "kubernetes" {
  host                   = "https://${data.azurerm_kubernetes_cluster.this.fqdn}:443"
  cluster_ca_certificate = base64decode(data.azurerm_kubernetes_cluster.this.kube_config[0].cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "kubelogin"
    # 6dae42f8-... is the well-known AKS Entra server application ID.
    args = ["get-token", "--login", var.kubelogin_mode, "--server-id", "6dae42f8-4368-4678-94ff-3960e28e3630"]
  }
}

provider "helm" {
  kubernetes = {
    host                   = "https://${data.azurerm_kubernetes_cluster.this.fqdn}:443"
    cluster_ca_certificate = base64decode(data.azurerm_kubernetes_cluster.this.kube_config[0].cluster_ca_certificate)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "kubelogin"
      args        = ["get-token", "--login", var.kubelogin_mode, "--server-id", "6dae42f8-4368-4678-94ff-3960e28e3630"]
    }
  }
}

data "azurerm_user_assigned_identity" "id" {
  for_each            = toset(["provisioning", "deployment", "platform-deploy", "backstage", "discovery", "orchestrator", "postgres", "tls-sync"])
  name                = "id-idp-${each.key}-${var.environment}"
  resource_group_name = var.identity_resource_group
}

locals {
  restricted = {
    "pod-security.kubernetes.io/enforce" = "restricted"
    "pod-security.kubernetes.io/audit"   = "restricted"
    "app.kubernetes.io/managed-by"       = "idp-platform"
  }
}

# ------------------------------------------------------------------ storage
# Disks created for volume claims get the landing zone's required tags. AKS's own storage classes
# create untagged disks, which a "require a tag on resources" policy denies (RequestDisallowedByPolicy,
# the claim stays Pending). Platform and application volumes use this class.
variable "disk_tags" {
  description = "Tags on dynamically created disks; must satisfy the landing zone's tag policy."
  type        = map(string)
  default = {
    "workload"           = "idp"
    "owner"              = "platform-team"
    "costCenter"         = "platform"
    "criticality"        = "low"
    "dataClassification" = "internal"
    "managed-by"         = "idp-platform"
  }
}

resource "kubernetes_storage_class_v1" "tagged" {
  metadata {
    name = "managed-csi-tagged"
  }
  storage_provisioner    = "disk.csi.azure.com"
  reclaim_policy         = "Delete"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  parameters = {
    skuName = "StandardSSD_LRS"
    tags    = join(",", [for k, v in merge(var.disk_tags, { "environment" = var.environment }) : "${k}=${v}"])
  }
}

locals {
  public_dns_label = coalesce(var.public_dns_label, "idp-${var.environment}-${substr(sha1(data.azurerm_kubernetes_cluster.this.id), 0, 6)}")
  public_host      = "${local.public_dns_label}.${data.azurerm_kubernetes_cluster.this.location}.cloudapp.azure.com"
  tls_secret       = var.gateway_tls_secret != null ? var.gateway_tls_secret : (var.public_tls ? "idp-public-tls" : null)
}

# ------------------------------------------------------------------ namespaces
# The Gateway's proxy pods are created and managed by AKS App Routing (Istio). Their istio-proxy
# container sets no seccomp profile, which "restricted" rejects, so this namespace enforces
# "baseline" (no privileged pods, host access or added capabilities) and still warns and audits
# against "restricted". Besides the proxies only the TLS pieces run here: cert-manager's short-lived
# ACME solver (its HTTPRoute attaches to the Gateway, hence gateway-access) and the tls-sync jobs.
resource "kubernetes_namespace_v1" "gateway" {
  metadata {
    name = "idp-gateway"
    labels = merge(local.restricted, {
      "pod-security.kubernetes.io/enforce" = "baseline"
      "pod-security.kubernetes.io/warn"    = "restricted"
      "idp.io/gateway-access"              = "true"
    })
  }
}

resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name   = "idp-platform"
    labels = merge(local.restricted, { "idp.io/gateway-access" = "true" })
  }
}

# ------------------------------------------------------------------ shared Gateway (ADR-0003)
resource "kubernetes_manifest" "gateway" {
  manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "Gateway"
    metadata = {
      name      = "idp-gateway"
      namespace = kubernetes_namespace_v1.gateway.metadata[0].name
      # The platform charts read this at deploy time (dns.mode auto) for Backstage and the GitHub hooks.
      annotations = { "idp.io/public-host" = local.public_host }
    }
    spec = {
      gatewayClassName = "approuting-istio"
      # App Routing copies these to the Gateway's LoadBalancer Service; Azure puts the label on its public IP.
      infrastructure = { annotations = { "service.beta.kubernetes.io/azure-dns-label-name" = local.public_dns_label } }
      listeners = concat(
        [{
          name     = "http"
          port     = 80
          protocol = "HTTP"
          hostname = var.gateway_hostname
          allowedRoutes = { namespaces = { from = "Selector", selector = {
          matchLabels = { "idp.io/gateway-access" = "true" } } } }
        }],
        local.tls_secret == null ? [] : [{
          name     = "https"
          port     = 443
          protocol = "HTTPS"
          hostname = var.gateway_hostname
          tls      = { mode = "Terminate", certificateRefs = [{ kind = "Secret", name = local.tls_secret }] }
          allowedRoutes = { namespaces = { from = "Selector", selector = {
          matchLabels = { "idp.io/gateway-access" = "true" } } } }
        }],
      )
    }
  }
}

# ------------------------------------------------------------------ RBAC
resource "kubernetes_cluster_role_v1" "app_deployer" {
  metadata {
    name = "idp-app-deployer"
  }
  rule {
    api_groups = ["", "apps"]
    resources  = ["deployments", "replicasets", "services", "serviceaccounts", "configmaps"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods", "pods/log", "events"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["autoscaling", "policy", "networking.k8s.io", "gateway.networking.k8s.io", "secrets-store.csi.x-k8s.io"]
    resources  = ["horizontalpodautoscalers", "poddisruptionbudgets", "networkpolicies", "httproutes", "secretproviderclasses"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
  # Deliberately no access to Secrets: Helm runs with HELM_DRIVER=configmap (ADR-0005).
}

resource "kubernetes_cluster_role_v1" "namespace_provisioner" {
  metadata {
    name = "idp-namespace-provisioner"
  }
  rule {
    api_groups = [""]
    resources  = ["namespaces"]
    verbs      = ["get", "list", "create", "update", "patch", "delete"]
  }
  rule {
    api_groups = [""]
    resources  = ["resourcequotas", "limitranges"]
    verbs      = ["get", "list", "create", "update", "patch", "delete"]
  }
  rule {
    api_groups = ["rbac.authorization.k8s.io"]
    resources  = ["rolebindings"]
    verbs      = ["get", "list", "create", "update", "patch", "delete"]
  }
  rule {
    # May only bind the deployer role, never anything broader.
    api_groups     = ["rbac.authorization.k8s.io"]
    resources      = ["clusterroles"]
    resource_names = [kubernetes_cluster_role_v1.app_deployer.metadata[0].name]
    verbs          = ["bind"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "provisioner" {
  metadata {
    name = "idp-namespace-provisioner"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.namespace_provisioner.metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "User"
    name      = data.azurerm_user_assigned_identity.id["provisioning"].principal_id
  }
}

resource "kubernetes_role_binding_v1" "platform_deployer" {
  metadata {
    name      = "platform-deployer"
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.app_deployer.metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "User"
    name      = data.azurerm_user_assigned_identity.id["platform-deploy"].principal_id
  }
}

# The orchestrator's Operations view (#115) reads what runs in the application namespaces: read-only,
# workloads and pods only. No Secrets, ConfigMaps, logs or exec. Best practice would bind it per
# application namespace (through the app-namespace module); one ClusterRoleBinding keeps the module
# and the generated repositories' pinned module versions unchanged.
resource "kubernetes_cluster_role_v1" "operations_reader" {
  metadata {
    name = "idp-operations-reader"
  }
  rule {
    api_groups = ["apps"]
    resources  = ["deployments", "replicasets"]
    verbs      = ["get", "list"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["get", "list"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "operations_reader" {
  metadata {
    name = "idp-operations-reader"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.operations_reader.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = "provisioning-orchestrator"
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
  }
}

# What the platform charts need beyond an application's deployer role, in idp-platform only: the
# orchestrator's migration Job (a Helm hook, deleted and re-created per release) and, in dev, the
# in-cluster PostgreSQL (StatefulSet, its volume claim, and its generated credentials Secret, which
# Helm reads back with lookup so the passwords survive upgrades).
resource "kubernetes_role_v1" "platform_jobs" {
  metadata {
    name      = "platform-jobs"
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
  }
  rule {
    api_groups = ["batch"]
    resources  = ["jobs"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
  rule {
    api_groups = ["apps"]
    resources  = ["statefulsets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
  rule {
    api_groups = [""]
    resources  = ["persistentvolumeclaims", "secrets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
}

resource "kubernetes_role_binding_v1" "platform_jobs" {
  metadata {
    name      = "platform-jobs"
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.platform_jobs.metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "User"
    name      = data.azurerm_user_assigned_identity.id["platform-deploy"].principal_id
  }
}

# platform-release reads the shared Gateway's public IP for <gateway-ip>.nip.io hostnames: read only, Gateways only.
resource "kubernetes_role_v1" "gateway_reader" {
  metadata {
    name      = "gateway-reader"
    namespace = kubernetes_namespace_v1.gateway.metadata[0].name
  }
  rule {
    api_groups = ["gateway.networking.k8s.io"]
    resources  = ["gateways"]
    verbs      = ["get"]
  }
}

resource "kubernetes_role_binding_v1" "gateway_reader" {
  metadata {
    name      = "gateway-reader"
    namespace = kubernetes_namespace_v1.gateway.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.gateway_reader.metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "User"
    name      = data.azurerm_user_assigned_identity.id["platform-deploy"].principal_id
  }
}

# ------------------------------------------------------------------ public TLS (cert-manager, Let's Encrypt)
# HTTP-01 through the Gateway for the stable public host. The certificate is kept in a dedicated Key
# Vault (10-identities) so a re-provision restores it instead of requesting a new one (Let's Encrypt
# allows 5 per week for the same name). Requests are small to fit the single 4-vCPU node.
resource "kubernetes_namespace_v1" "cert_manager" {
  count = var.public_tls ? 1 : 0
  metadata {
    name   = "cert-manager"
    labels = local.restricted
  }
}

resource "helm_release" "cert_manager" {
  count      = var.public_tls ? 1 : 0
  name       = "cert-manager"
  repository = "oci://quay.io/jetstack/charts" # OCI: no repository index to fetch or cache
  chart      = "cert-manager"
  version    = "v1.21.2"
  namespace  = kubernetes_namespace_v1.cert_manager[0].metadata[0].name
  wait       = true
  values = [yamlencode({
    crds            = { enabled = true }
    config          = { apiVersion = "controller.config.cert-manager.io/v1alpha1", kind = "ControllerConfiguration", enableGatewayAPI = true }
    resources       = { requests = { cpu = "10m", memory = "48Mi" } }
    webhook         = { resources = { requests = { cpu = "10m", memory = "32Mi" } } }
    cainjector      = { resources = { requests = { cpu = "10m", memory = "48Mi" } } }
    startupapicheck = { enabled = false }
    prometheus      = { enabled = false }
    global          = { leaderElection = { namespace = "cert-manager" } }
  })]
}

# The certificate's Key Vault copy: the tls-sync identity may manage secrets in that vault only.
data "azurerm_resources" "tls_vault" {
  count               = var.public_tls ? 1 : 0
  type                = "Microsoft.KeyVault/vaults"
  resource_group_name = var.identity_resource_group
  required_tags       = { idpPurpose = "public-tls" }
}

resource "kubernetes_service_account_v1" "tls_sync" {
  count = var.public_tls ? 1 : 0
  metadata {
    name        = "tls-sync"
    namespace   = kubernetes_namespace_v1.gateway.metadata[0].name
    annotations = { "azure.workload.identity/client-id" = data.azurerm_user_assigned_identity.id["tls-sync"].client_id }
  }
  automount_service_account_token = true # the sync jobs call the Kubernetes API for the one Secret
}

resource "kubernetes_role_v1" "tls_sync" {
  count = var.public_tls ? 1 : 0
  metadata {
    name      = "tls-sync"
    namespace = kubernetes_namespace_v1.gateway.metadata[0].name
  }
  rule {
    api_groups     = [""]
    resources      = ["secrets"]
    resource_names = [local.tls_secret]
    verbs          = ["get"]
  }
  rule {
    # create can't be limited by name; this namespace holds only the TLS Secrets.
    api_groups = [""]
    resources  = ["secrets"]
    verbs      = ["create"]
  }
}

resource "kubernetes_role_binding_v1" "tls_sync" {
  count = var.public_tls ? 1 : 0
  metadata {
    name      = "tls-sync"
    namespace = kubernetes_namespace_v1.gateway.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.tls_sync[0].metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.tls_sync[0].metadata[0].name
    namespace = kubernetes_namespace_v1.gateway.metadata[0].name
  }
}

resource "azurerm_federated_identity_credential" "tls_sync" {
  count                     = var.public_tls ? 1 : 0
  name                      = "k8s-idp-gateway-tls-sync"
  user_assigned_identity_id = data.azurerm_user_assigned_identity.id["tls-sync"].id
  issuer                    = data.azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject                   = "system:serviceaccount:idp-gateway:tls-sync"
  audience                  = ["api://AzureADTokenExchange"]
}

resource "helm_release" "platform_tls" {
  count         = var.public_tls ? 1 : 0
  name          = "platform-tls"
  chart         = "${path.module}/../../../deploy/charts/platform-tls"
  namespace     = kubernetes_namespace_v1.gateway.metadata[0].name
  wait          = true
  wait_for_jobs = true
  values = [yamlencode({
    host       = local.public_host
    secretName = local.tls_secret
    acme       = { email = var.acme_email }
    keyVault   = { name = data.azurerm_resources.tls_vault[0].resources[0].name }
  })]
  # Restore needs its identity and Kubernetes access first; the issuer needs cert-manager's CRDs.
  depends_on = [
    helm_release.cert_manager,
    kubernetes_role_binding_v1.tls_sync,
    azurerm_federated_identity_credential.tls_sync,
    kubernetes_manifest.gateway,
  ]
}

# ------------------------------------------------------------------ Workload Identity for platform services
resource "azurerm_federated_identity_credential" "service" {
  for_each                  = toset(["backstage", "discovery", "orchestrator", "postgres"])
  name                      = "k8s-idp-platform-${each.key}"
  user_assigned_identity_id = data.azurerm_user_assigned_identity.id[each.key].id
  issuer                    = data.azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject                   = "system:serviceaccount:idp-platform:${each.key == "discovery" ? "azure-discovery" : each.key == "orchestrator" ? "provisioning-orchestrator" : each.key}"
  audience                  = ["api://AzureADTokenExchange"]
}

output "public_host" {
  description = "Stable public name for Backstage and the GitHub hooks (the GitHub App callback and webhook URLs)."
  value       = local.public_host
}

output "gateway" {
  value = { name = "idp-gateway", namespace = "idp-gateway" }
}
