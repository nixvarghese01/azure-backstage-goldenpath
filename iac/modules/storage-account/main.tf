# Storage account with secure defaults: Entra-only data access (no shared keys), TLS 1.2+,
# no public blob access. Zone-redundant when the availability tier is "ha" (ADR-0004).

variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.name))
    error_message = "Storage account names are 3-24 lowercase letters or digits."
  }
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "availability_tier" {
  type    = string
  default = "standard"
  validation {
    condition     = contains(["standard", "ha"], var.availability_tier)
    error_message = "availability_tier must be standard or ha."
  }
}

variable "public_network_access_enabled" {
  description = "Model project default: true with Entra-only auth. Production: false with private endpoints."
  type        = bool
  default     = true
}

variable "containers" {
  type    = list(string)
  default = ["app-data"]
}

variable "tags" {
  type = map(string)
}

resource "azurerm_storage_account" "this" {
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys; customer-managed keys are out of scope.
  #checkov:skip=CKV2_AZURE_33:Private endpoints need private networking for runners and pods; shared keys are disabled (Entra only).
  #checkov:skip=CKV_AZURE_59:Public network access with Entra-only data access; private endpoints in production.
  #checkov:skip=CKV_AZURE_33:No queues are used; blob only.
  #checkov:skip=CKV_AZURE_206:Replication follows the availability tier (ADR-0004): LRS for standard, ZRS for ha.
  name                            = var.name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = var.availability_tier == "ha" ? "ZRS" : "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  local_user_enabled              = false # SFTP/local users: Entra only (CKV_AZURE_244)
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = var.public_network_access_enabled
  tags                            = var.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "this" {
  #checkov:skip=CKV2_AZURE_21:Blob read logging needs a diagnostic setting and Log Analytics workspace; not enabled in the demo.
  for_each              = toset(var.containers)
  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

output "id" {
  value = azurerm_storage_account.this.id
}

output "name" {
  value = azurerm_storage_account.this.name
}

output "blob_endpoint" {
  value = azurerm_storage_account.this.primary_blob_endpoint
}
