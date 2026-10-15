mock_provider "azurerm" {}

variables {
  name                = "psql-idp-dev"
  resource_group_name = "rg-idp-data-dev"
  location            = "swedencentral"
  tenant_id           = "00000000-0000-0000-0000-000000000000"
  entra_admin         = { object_id = "11111111-1111-1111-1111-111111111111", principal_name = "id-idp-platform-dev", principal_type = "ServicePrincipal" }
  tags                = { "managed-by" = "idp-platform" }
}

run "entra_only_one_database_per_service" {
  command = plan
  assert {
    condition     = azurerm_postgresql_flexible_server.this.authentication[0].password_auth_enabled == false
    error_message = "password authentication must be off (Entra only)"
  }
  assert {
    condition     = azurerm_postgresql_flexible_server.this.authentication[0].active_directory_auth_enabled == true
    error_message = "Entra authentication must be on"
  }
  assert {
    condition     = toset(keys(azurerm_postgresql_flexible_server_database.db)) == toset(["backstage", "orchestrator"])
    error_message = "one database per service"
  }
  assert {
    condition     = azurerm_postgresql_flexible_server.this.backup_retention_days == 7
    error_message = "7-day backups"
  }
}

run "firewall_rules_only_with_public_access" {
  command = plan
  variables {
    public_network_access_enabled = false
    allowed_ips                   = { aks = "20.0.0.1" }
  }
  assert {
    condition     = length(azurerm_postgresql_flexible_server_firewall_rule.allowed) == 0
    error_message = "a private server must not get firewall rules"
  }
}
