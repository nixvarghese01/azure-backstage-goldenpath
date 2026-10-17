# Azure: OIDC from GitHub Actions (ARM_USE_OIDC) as the provisioning identity; no client secrets.
provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

# Kubernetes: the existing shared cluster, Entra auth through kubelogin (az login session).
data "azurerm_kubernetes_cluster" "target" {
  name                = var.aks_cluster.name
  resource_group_name = var.aks_cluster.resource_group
}

provider "kubernetes" {
  host                   = "https://${data.azurerm_kubernetes_cluster.target.fqdn}:443"
  cluster_ca_certificate = base64decode(data.azurerm_kubernetes_cluster.target.kube_config[0].cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "kubelogin"
    args        = ["get-token", "--login", "azurecli", "--server-id", "6dae42f8-4368-4678-94ff-3960e28e3630"]
  }
}
