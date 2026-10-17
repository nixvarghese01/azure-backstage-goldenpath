terraform {
  required_version = ">= 1.16.0, < 2.0.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.9.0, < 6.0.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = ">= 2.13.0, < 3.0.0"
    }
  }
}
