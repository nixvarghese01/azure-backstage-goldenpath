# Application runtime identity: a user-assigned managed identity federated to one Kubernetes service
# account through Microsoft Entra Workload Identity. Separate from infrastructure and deploy identities.

variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "oidc_issuer_url" {
  description = "AKS OIDC issuer URL."
  type        = string
  validation {
    condition     = startswith(var.oidc_issuer_url, "https://")
    error_message = "oidc_issuer_url must be an https URL."
  }
}

variable "namespace" {
  type = string
}

variable "service_account" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "azurerm_user_assigned_identity" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "workload" {
  name                      = "k8s-${var.namespace}-${var.service_account}"
  user_assigned_identity_id = azurerm_user_assigned_identity.this.id
  issuer                    = var.oidc_issuer_url
  subject                   = "system:serviceaccount:${var.namespace}:${var.service_account}"
  audience                  = ["api://AzureADTokenExchange"]
}

output "id" {
  value = azurerm_user_assigned_identity.this.id
}

output "client_id" {
  description = "Goes into the ServiceAccount annotation azure.workload.identity/client-id."
  value       = azurerm_user_assigned_identity.this.client_id
}

output "principal_id" {
  value = azurerm_user_assigned_identity.this.principal_id
}
