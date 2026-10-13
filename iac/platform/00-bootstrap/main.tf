# Terraform state storage (ADR-0002 §7). Applied once with local state, then migrated into itself.

terraform {
  required_version = "~> 1.16.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
  }
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "uksouth"
}

variable "name_suffix" {
  description = "Optional suffix to make the globally unique storage account name available."
  type        = string
  default     = ""
  validation {
    condition     = can(regex("^[a-z0-9]{0,4}$", var.name_suffix))
    error_message = "name_suffix must be up to 4 lowercase letters or digits."
  }
}

locals {
  tags = {
    "managed-by"  = "sportify-platform"
    "environment" = var.environment
    "lifecycle"   = "platform"
    "application" = "sportify-platform"
    "owner"       = "platform-team"
  }
}

resource "azurerm_resource_group" "state" {
  name     = "rg-sportify-tfstate-${var.environment}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "state" {
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys; customer-managed keys are out of scope.
  #checkov:skip=CKV2_AZURE_33:Private endpoints need private networking for runners and pods; shared keys are disabled (Entra only).
  #checkov:skip=CKV_AZURE_59:Public network access with Entra-only data access; private endpoints in production.
  #checkov:skip=CKV_AZURE_33:No queues are used; blob only.
  name                            = "stsportifytfstate${var.environment}${var.name_suffix}"
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "GZRS" # state must survive a zone or region outage
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  tags                            = local.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "state" {
  #checkov:skip=CKV2_AZURE_21:Blob read logging needs a diagnostic setting and Log Analytics workspace; versioning and a delete lock protect state.
  for_each              = toset(["platform", "apps"])
  name                  = each.value
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

resource "azurerm_management_lock" "state" {
  name       = "do-not-delete-terraform-state"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Terraform state for Sportify Azure Backstage. Remove only during full teardown."
}

output "storage_account_name" {
  value = azurerm_storage_account.state.name
}

output "storage_account_id" {
  value = azurerm_storage_account.state.id
}

output "resource_group_name" {
  value = azurerm_resource_group.state.name
}
