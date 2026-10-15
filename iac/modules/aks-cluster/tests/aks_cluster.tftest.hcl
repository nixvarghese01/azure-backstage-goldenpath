mock_provider "azurerm" {}
mock_provider "azapi" {}

variables {
  name                   = "aks-idp-shared-dev"
  resource_group_name    = "rg-idp-aks-dev"
  location               = "swedencentral"
  kubernetes_version     = "1.34"
  tenant_id              = "00000000-0000-0000-0000-000000000000"
  admin_group_object_ids = ["11111111-1111-1111-1111-111111111111"]
  system_pool            = { vm_size = "Standard_B4s_v2", node_count = 1, os_disk_size_gb = 30 }
  node_resource_group    = "rg-idp-aks-nodes-dev"
  tags                   = { "workload" = "idp", "environment" = "dev", "owner" = "platform-team" }
}

run "secure_defaults" {
  command = plan
  assert {
    condition     = azurerm_kubernetes_cluster.this.local_account_disabled == true
    error_message = "local accounts must be disabled (Entra only)"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.oidc_issuer_enabled && azurerm_kubernetes_cluster.this.workload_identity_enabled
    error_message = "Workload Identity needs the OIDC issuer and the add-on"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.azure_active_directory_role_based_access_control[0].azure_rbac_enabled == false
    error_message = "the platform uses Kubernetes RBAC bound to Entra object IDs (ADR-0002)"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.default_node_pool[0].host_encryption_enabled == true
    error_message = "host encryption must be on"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.network_profile[0].network_policy == "cilium"
    error_message = "network policies need Cilium"
  }
}

run "landing_zone_fit" {
  command = plan
  assert {
    condition     = azurerm_kubernetes_cluster.this.default_node_pool[0].tags["owner"] == "platform-team"
    error_message = "the node pool (scale set) must carry the tags: tag policies deny untagged scale sets"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.node_resource_group == "rg-idp-aks-nodes-dev"
    error_message = "the node resource group follows the landing zone naming"
  }
  assert {
    condition     = azurerm_kubernetes_cluster.this.default_node_pool[0].os_disk_size_gb == 30
    error_message = "the OS disk size must follow the input"
  }
}

run "single_pool_runs_system_and_apps" {
  command = plan
  assert {
    condition     = azurerm_kubernetes_cluster.this.default_node_pool[0].only_critical_addons_enabled == false
    error_message = "without a user pool, applications must be allowed on the system pool"
  }
  assert {
    condition     = length(azurerm_kubernetes_cluster_node_pool.user) == 0
    error_message = "no user pool unless asked for"
  }
}

run "gateway_api_without_the_default_nginx" {
  command = plan
  assert {
    condition     = azapi_update_resource.gateway_api[0].body.properties.ingressProfile.webAppRouting.nginx.defaultIngressControllerType == "None"
    error_message = "the default nginx controller must stay off (about 1 vCPU on a small node)"
  }
  assert {
    condition     = azapi_update_resource.gateway_api[0].body.properties.ingressProfile.gatewayAPI.installation == "Standard"
    error_message = "the managed Gateway API CRDs must be installed"
  }
}

run "ha_adds_a_zonal_user_pool" {
  command = plan
  variables {
    user_pool = { vm_size = "Standard_D2s_v5", node_count = 3, zones = ["1", "2", "3"] }
  }
  assert {
    condition     = length(azurerm_kubernetes_cluster_node_pool.user) == 1 && azurerm_kubernetes_cluster.this.default_node_pool[0].only_critical_addons_enabled
    error_message = "with a user pool, the system pool runs only critical add-ons"
  }
}

run "rejects_an_unknown_sku_tier" {
  command = plan
  variables {
    sku_tier = "Premium"
  }
  expect_failures = [var.sku_tier]
}
