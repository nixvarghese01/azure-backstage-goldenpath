mock_provider "azurerm" {}

variables {
  name                = "kv-orders-api-dev"
  resource_group_name = "rg-idp-apps-dev"
  location            = "swedencentral"
  tenant_id           = "00000000-0000-0000-0000-000000000000"
  tags                = { "managed-by" = "idp-platform" }
}

run "rbac_purge_protection_and_short_demo_retention" {
  command = plan
  assert {
    condition     = azurerm_key_vault.this.rbac_authorization_enabled == true
    error_message = "access must be Entra RBAC, not access policies"
  }
  assert {
    condition     = azurerm_key_vault.this.purge_protection_enabled == true
    error_message = "purge protection must be on"
  }
  assert {
    condition     = azurerm_key_vault.this.soft_delete_retention_days == 7
    error_message = "demo vaults keep deleted secrets 7 days by default"
  }
  assert {
    condition     = azurerm_key_vault.this.sku_name == "standard"
    error_message = "standard SKU"
  }
}

run "private_vault" {
  command = plan
  variables {
    public_network_access_enabled = false
    soft_delete_retention_days    = 90
  }
  assert {
    condition     = azurerm_key_vault.this.public_network_access_enabled == false
    error_message = "public access must follow the input"
  }
}

run "rejects_retention_outside_7_to_90_days" {
  command = plan
  variables {
    soft_delete_retention_days = 3
  }
  expect_failures = [var.soft_delete_retention_days]
}

run "rejects_an_invalid_name" {
  command = plan
  variables {
    name = "kv_orders"
  }
  expect_failures = [var.name]
}
