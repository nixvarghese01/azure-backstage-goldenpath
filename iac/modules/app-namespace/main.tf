# Application namespace with quota, default limits and the deployer RoleBinding (ADR-0002 §9).
# Workloads themselves are deployed by Helm, not Terraform.

variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$", var.name)) && !startswith(var.name, "kube-")
    error_message = "Namespace must be a DNS label and not start with kube-."
  }
}

variable "owner" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "deployer_principal_id" {
  description = "Object ID of the deployment identity allowed to deploy into this namespace."
  type        = string
}

variable "availability_tier" {
  type    = string
  default = "standard"
}

locals {
  quota = var.availability_tier == "ha" ? {
    "requests.cpu" = "2", "requests.memory" = "4Gi", "limits.cpu" = "4", "limits.memory" = "8Gi", "pods" = "20"
    } : {
    "requests.cpu" = "1", "requests.memory" = "2Gi", "limits.cpu" = "2", "limits.memory" = "4Gi", "pods" = "10"
  }
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name = var.name
    labels = merge(var.labels, {
      "sportify.io/owner"                  = var.owner
      "sportify.io/gateway-access"         = "true"
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
      "app.kubernetes.io/managed-by"       = "sportify-platform"
    })
  }
}

resource "kubernetes_resource_quota_v1" "default" {
  metadata {
    name      = "default"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    hard = local.quota
  }
}

resource "kubernetes_limit_range_v1" "default" {
  metadata {
    name      = "default"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    limit {
      type            = "Container"
      default         = { cpu = "500m", memory = "512Mi" }
      default_request = { cpu = "100m", memory = "128Mi" }
    }
  }
}

resource "kubernetes_role_binding_v1" "deployer" {
  metadata {
    name      = "deployer"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "sportify-app-deployer"
  }
  subject {
    # AKS with Entra integration maps a managed identity to its object ID.
    api_group = "rbac.authorization.k8s.io"
    kind      = "User"
    name      = var.deployer_principal_id
  }
}

output "name" {
  value = kubernetes_namespace_v1.this.metadata[0].name
}
