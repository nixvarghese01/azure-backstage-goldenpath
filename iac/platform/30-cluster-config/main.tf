# In-cluster platform configuration for an EXISTING cluster (never created in the same config):
# namespaces, the shared Gateway (ADR-0003), ClusterRoles/bindings for the provisioning and deployment
# identities (ADR-0002 §9), and Workload Identity federation for the platform services.

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

variable "gateway_tls_secret" {
  description = "Name of a TLS Secret/certificate reference for an HTTPS listener. null = HTTP only (demo)."
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

data "azurerm_user_assigned_identity" "id" {
  for_each            = toset(["provisioning", "deployment", "platform-deploy", "backstage", "discovery", "orchestrator", "postgres"])
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
}

# ------------------------------------------------------------------ namespaces
# The Gateway's proxy pods are created and managed by AKS App Routing (Istio). Their istio-proxy
# container sets no seccomp profile, which "restricted" rejects, so this namespace enforces
# "baseline" (no privileged pods, host access or added capabilities) and still warns and audits
# against "restricted". Nothing else runs here.
resource "kubernetes_namespace_v1" "gateway" {
  metadata {
    name = "idp-gateway"
    labels = merge(local.restricted, {
      "pod-security.kubernetes.io/enforce" = "baseline"
      "pod-security.kubernetes.io/warn"    = "restricted"
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
        var.gateway_tls_secret == null ? [] : [{
          name     = "https"
          port     = 443
          protocol = "HTTPS"
          hostname = var.gateway_hostname
          tls      = { mode = "Terminate", certificateRefs = [{ kind = "Secret", name = var.gateway_tls_secret }] }
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
