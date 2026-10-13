# A user-assigned identity that GitHub Actions can use through OIDC federation (no client secrets).
# Subjects are bound to environments and, for generated repositories, to the platform's reviewed
# reusable workflow (ADR-0005), using the organisation's customised OIDC subject claim.

variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "subjects" {
  description = "Map of credential name -> GitHub OIDC subject."
  type        = map(string)
  validation {
    condition     = length(var.subjects) <= 20
    error_message = "A managed identity supports at most 20 federated credentials."
  }
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

resource "azurerm_federated_identity_credential" "github" {
  for_each                  = var.subjects
  name                      = each.key
  user_assigned_identity_id = azurerm_user_assigned_identity.this.id
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = each.value
  audience                  = ["api://AzureADTokenExchange"]
}

output "id" {
  value = azurerm_user_assigned_identity.this.id
}

output "client_id" {
  value = azurerm_user_assigned_identity.this.client_id
}

output "principal_id" {
  value = azurerm_user_assigned_identity.this.principal_id
}
