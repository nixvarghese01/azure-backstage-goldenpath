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
  default = "aks-sportify-shared-dev"
}

variable "cluster_resource_group" {
  type    = string
  default = "rg-sportify-platform-dev"
}

variable "identity_resource_group" {
  type    = string
  default = "rg-sportify-identities-dev"
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
  for_each            = toset(["provisioning", "deployment", "platform-deploy", "backstage", "discovery", "orchestrator"])
  name                = "id-sportify-${each.key}-${var.environment}"
  resource_group_name = var.identity_resource_group
}

locals {
  restricted = {
    "pod-security.kubernetes.io/enforce" = "restricted"
    "pod-security.kubernetes.io/audit"   = "restricted"
    "app.kubernetes.io/managed-by"       = "sportify-platform"
  }
}

# ------------------------------------------------------------------ namespaces
resource "kubernetes_namespace_v1" "gateway" {
  metadata {
    name   = "sportify-gateway"
    labels = local.restricted
  }
}

resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name   = "sportify-platform"
    labels = merge(local.restricted, { "sportify.io/gateway-access" = "true" })
  }
}

# ------------------------------------------------------------------ shared Gateway (ADR-0003)
resource "kubernetes_manifest" "gateway" {
  manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "Gateway"
    metadata = {
      name      = "sportify-gateway"
      namespace = kubernetes_namespace_v1.gateway.metadata[0].name
    }
    spec = {
      gatewayClassName = "approuting-istio"
      listeners = concat(
        [{
          name     = "http"
          port     = 80
          protocol = "HTTP"
          hostname = var.gateway_hostname
          allowedRoutes = { namespaces = { from = "Selector", selector = {
          matchLabels = { "sportify.io/gateway-access" = "true" } } } }
        }],
        var.gateway_tls_secret == null ? [] : [{
          name     = "https"
          port     = 443
          protocol = "HTTPS"
          hostname = var.gateway_hostname
          tls      = { mode = "Terminate", certificateRefs = [{ kind = "Secret", name = var.gateway_tls_secret }] }
          allowedRoutes = { namespaces = { from = "Selector", selector = {
          matchLabels = { "sportify.io/gateway-access" = "true" } } } }
        }],
      )
    }
  }
}

# ------------------------------------------------------------------ RBAC
resource "kubernetes_cluster_role_v1" "app_deployer" {
  metadata {
    name = "sportify-app-deployer"
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
    name = "sportify-namespace-provisioner"
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
    name = "sportify-namespace-provisioner"
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

# ------------------------------------------------------------------ Workload Identity for platform services
resource "azurerm_federated_identity_credential" "service" {
  for_each                  = toset(["backstage", "discovery", "orchestrator"])
  name                      = "k8s-sportify-platform-${each.key}"
  user_assigned_identity_id = data.azurerm_user_assigned_identity.id[each.key].id
  issuer                    = data.azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject                   = "system:serviceaccount:sportify-platform:${each.key == "discovery" ? "azure-discovery" : each.key == "orchestrator" ? "provisioning-orchestrator" : each.key}"
  audience                  = ["api://AzureADTokenExchange"]
}

output "gateway" {
  value = { name = "sportify-gateway", namespace = "sportify-gateway" }
}
