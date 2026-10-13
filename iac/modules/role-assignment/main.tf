# Role assignment restricted to an allowlist of roles (policies/allowlist.yaml -> roles.assignable).

variable "scope" {
  type = string
}

variable "role_definition_name" {
  type = string
}

variable "principal_id" {
  type = string
}

variable "allowed_roles" {
  type = list(string)
  default = [
    "Storage Blob Data Contributor",
    "Storage Blob Data Reader",
    "Key Vault Secrets User",
  ]
}

resource "terraform_data" "role_allowed" {
  lifecycle {
    precondition {
      condition     = contains(var.allowed_roles, var.role_definition_name)
      error_message = "Role '${var.role_definition_name}' is not on the platform's assignable-role allowlist."
    }
  }
}

resource "azurerm_role_assignment" "this" {
  scope                = var.scope
  role_definition_name = var.role_definition_name
  principal_id         = var.principal_id
  principal_type       = "ServicePrincipal"
  depends_on           = [terraform_data.role_allowed]
}

output "id" {
  value = azurerm_role_assignment.this.id
}
