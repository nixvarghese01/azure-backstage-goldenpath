# Shared AKS cluster (never one per application). OIDC issuer + Workload Identity, Entra auth with local
# accounts disabled, Kubernetes RBAC, Azure CNI Overlay with Cilium, Key Vault secrets provider with
# rotation, and the App Routing Gateway API implementation (ADR-0003) enabled through azapi.

variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

variable "sku_tier" {
  description = "Free (no uptime SLA; demo) or Standard (SLA)."
  type        = string
  default     = "Free"
  validation {
    condition     = contains(["Free", "Standard"], var.sku_tier)
    error_message = "sku_tier must be Free or Standard."
  }
}

variable "tenant_id" {
  type = string
}

variable "admin_group_object_ids" {
  description = "Entra groups with cluster-admin (break-glass, platform team)."
  type        = list(string)
}

variable "system_pool" {
  type = object({
    vm_size    = string
    node_count = number
    zones      = optional(list(string), [])
  })
  default = { vm_size = "Standard_D2s_v5", node_count = 1 }
}

variable "user_pool" {
  description = "Optional zone-spanning user pool for HA workloads (ADR-0004). null = none."
  type = object({
    vm_size    = string
    node_count = number
    zones      = list(string)
  })
  default = null
}

variable "enable_gateway_api" {
  type    = bool
  default = true
}

variable "tags" {
  type = map(string)
}

resource "azurerm_kubernetes_cluster" "this" {
  name                      = var.name
  location                  = var.location
  resource_group_name       = var.resource_group_name
  dns_prefix                = var.name
  kubernetes_version        = var.kubernetes_version
  sku_tier                  = var.sku_tier
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  local_account_disabled    = true
  automatic_upgrade_channel = "patch"
  node_os_upgrade_channel   = "NodeImage"
  tags                      = var.tags

  default_node_pool {
    name                         = "system"
    vm_size                      = var.system_pool.vm_size
    node_count                   = var.system_pool.node_count
    zones                        = var.system_pool.zones
    only_critical_addons_enabled = var.user_pool != null
    upgrade_settings {
      max_surge = "10%"
    }
  }

  # azurerm 5 requires this block; node pools are managed explicitly, not auto-provisioned.
  node_provisioning_profile {
    mode = "Manual"
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    tenant_id              = var.tenant_id
    admin_group_object_ids = var.admin_group_object_ids
    azure_rbac_enabled     = false # Kubernetes RBAC: RoleBindings to Entra object IDs (ADR-0002 §9)
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_data_plane  = "cilium"
    network_policy      = "cilium"
    load_balancer_sku   = "standard"
  }

  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  lifecycle {
    ignore_changes = [kubernetes_version] # upgrades are deliberate, see COMPATIBILITY.md
  }
}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  count                 = var.user_pool == null ? 0 : 1
  name                  = "user"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.user_pool.vm_size
  node_count            = var.user_pool.node_count
  zones                 = var.user_pool.zones
  mode                  = "User"
  tags                  = var.tags
}

# Managed Gateway API CRDs + App Routing Istio implementation (not yet exposed natively by azurerm).
resource "azapi_update_resource" "gateway_api" {
  count       = var.enable_gateway_api ? 1 : 0
  type        = "Microsoft.ContainerService/managedClusters@2026-03-01"
  resource_id = azurerm_kubernetes_cluster.this.id
  body = {
    properties = {
      ingressProfile = {
        gatewayAPI = { installation = "Standard" }
        webAppRouting = {
          enabled                   = true
          gatewayAPIImplementations = { appRoutingIstio = { mode = "Enabled" } }
        }
      }
    }
  }
  depends_on = [azurerm_kubernetes_cluster_node_pool.user]
}

output "id" {
  value = azurerm_kubernetes_cluster.this.id
}

output "name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "oidc_issuer_url" {
  value = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "kubelet_object_id" {
  value = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

output "host" {
  description = "API server FQDN (not a credential)."
  value       = azurerm_kubernetes_cluster.this.fqdn
}

output "secrets_provider_identity_client_id" {
  value = azurerm_kubernetes_cluster.this.key_vault_secrets_provider[0].secret_identity[0].client_id
}
