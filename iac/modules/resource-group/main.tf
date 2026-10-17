variable "name" {
  type = string
  validation {
    condition     = can(regex("^rg-[a-z0-9-]{2,80}$", var.name))
    error_message = "Resource group names must look like rg-<name>."
  }
}

variable "location" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "azurerm_resource_group" "this" {
  name     = var.name
  location = var.location
  tags     = var.tags
}

output "id" {
  value = azurerm_resource_group.this.id
}

output "name" {
  value = azurerm_resource_group.this.name
}

output "location" {
  value = azurerm_resource_group.this.location
}
