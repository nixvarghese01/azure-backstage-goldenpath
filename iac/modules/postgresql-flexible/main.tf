# Azure Database for PostgreSQL flexible server with Entra-only authentication (no passwords).
# One database per service (data ownership rule). Service logins are mapped to their workload
# identities by scripts/postgres-grant-identities.sql (run once by the Entra admin).

variable "name" {
  type = string
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

variable "sku_name" {
  description = "Smallest Burstable size for the demo."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "zone" {
  description = <<-EOT
    Availability zone (1, 2 or 3), or null to let Azure choose. Pin one when the region reports
    RegionalAllocationFailed for the chosen size: capacity is often short in a single zone.
  EOT
  type        = string
  default     = null
}

variable "storage_mb" {
  type    = number
  default = 32768
}

variable "databases" {
  type    = list(string)
  default = ["backstage", "orchestrator"]
}

variable "entra_admin" {
  description = "Entra principal that administers the server (the platform identity)."
  type = object({
    object_id      = string
    principal_name = string
    principal_type = string # ServicePrincipal | Group | User
  })
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "allowed_ips" {
  description = "Firewall rules (e.g. AKS egress IP) when public access is enabled."
  type        = map(string)
  default     = {}
}

variable "tags" {
  type = map(string)
}

resource "azurerm_postgresql_flexible_server" "this" {
  #checkov:skip=CKV2_AZURE_57:Private access is configurable (public_network_access_enabled); demo uses a firewall allowlist with Entra-only auth.
  #checkov:skip=CKV_AZURE_136:Geo-redundant backups cost extra and are not needed for the demo; 7-day local backups are kept.
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "17"
  sku_name                      = var.sku_name
  zone                          = var.zone
  storage_mb                    = var.storage_mb
  backup_retention_days         = 7
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = var.tenant_id
  }

  lifecycle {
    ignore_changes = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "admin" {
  server_name         = azurerm_postgresql_flexible_server.this.name
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  object_id           = var.entra_admin.object_id
  principal_name      = var.entra_admin.principal_name
  principal_type      = var.entra_admin.principal_type
}

resource "azurerm_postgresql_flexible_server_database" "db" {
  for_each  = toset(var.databases)
  name      = each.value
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allowed" {
  for_each         = var.public_network_access_enabled ? var.allowed_ips : {}
  name             = each.key
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = each.value
  end_ip_address   = each.value
}

output "id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}
