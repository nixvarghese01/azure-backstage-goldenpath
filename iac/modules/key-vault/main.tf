# Key Vault in RBAC mode with purge protection and soft delete.

variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.name))
    error_message = "Key Vault names are 3-24 letters, digits or hyphens."
  }
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "soft_delete_retention_days" {
  description = "7 for demo vaults so the name is released soon after teardown; 90 in production."
  type        = number
  default     = 7
  validation {
    condition     = var.soft_delete_retention_days >= 7 && var.soft_delete_retention_days <= 90
    error_message = "Retention must be 7-90 days."
  }
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type = map(string)
}

resource "azurerm_key_vault" "this" {
  #checkov:skip=CKV2_AZURE_32:Private endpoints need private networking for runners; access is Entra RBAC only.
  #checkov:skip=CKV_AZURE_109:AKS reaches the vault from dynamic egress IPs; set public_network_access_enabled=false with a private endpoint in production.
  #checkov:skip=CKV_AZURE_189:Public network access is configurable (public_network_access_enabled); demo default is on with RBAC.
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = var.soft_delete_retention_days
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags
}

output "id" {
  value = azurerm_key_vault.this.id
}

output "name" {
  value = azurerm_key_vault.this.name
}

output "uri" {
  value = azurerm_key_vault.this.vault_uri
}
