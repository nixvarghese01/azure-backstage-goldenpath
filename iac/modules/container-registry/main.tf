variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9]{5,50}$", var.name))
    error_message = "Registry names are 5-50 letters or digits."
  }
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  type    = string
  default = "Basic"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "sku must be Basic, Standard or Premium."
  }
}

variable "tags" {
  type = map(string)
}

resource "azurerm_container_registry" "this" {
  # Basic SKU for the demo. The features below need Premium or Defender for Containers.
  #checkov:skip=CKV_AZURE_139:Public endpoint with Entra auth (admin user off); private access needs Premium.
  #checkov:skip=CKV_AZURE_163:Images are scanned with Trivy in CI before push; Defender for Containers is a paid add-on.
  #checkov:skip=CKV_AZURE_164:Docker Content Trust is deprecated; images carry GitHub build provenance attestations instead.
  #checkov:skip=CKV_AZURE_165:Geo-replication needs Premium; single-region platform.
  #checkov:skip=CKV_AZURE_166:Quarantine needs Premium; CI blocks images with critical vulnerabilities before push.
  #checkov:skip=CKV_AZURE_167:Retention policies need Premium; untagged manifests are cleaned up manually.
  #checkov:skip=CKV_AZURE_233:Zone redundancy needs Premium.
  #checkov:skip=CKV_AZURE_237:Dedicated data endpoints need Premium.
  name                   = var.name
  resource_group_name    = var.resource_group_name
  location               = var.location
  sku                    = var.sku
  admin_enabled          = false
  anonymous_pull_enabled = false
  tags                   = var.tags
}

output "id" {
  value = azurerm_container_registry.this.id
}

output "name" {
  value = azurerm_container_registry.this.name
}

output "login_server" {
  value = azurerm_container_registry.this.login_server
}
