mock_provider "azurerm" {}

variables {
  name                = "stordersapidev"
  resource_group_name = "rg-sportify-apps-dev"
  location            = "uksouth"
  tags                = { "managed-by" = "sportify-platform" }
}

run "standard_is_lrs_without_shared_keys" {
  command = plan
  assert {
    condition     = azurerm_storage_account.this.account_replication_type == "LRS"
    error_message = "standard tier must use LRS"
  }
  assert {
    condition     = azurerm_storage_account.this.shared_access_key_enabled == false
    error_message = "shared keys must be disabled"
  }
}

run "ha_is_zrs" {
  command = plan
  variables {
    availability_tier = "ha"
  }
  assert {
    condition     = azurerm_storage_account.this.account_replication_type == "ZRS"
    error_message = "ha tier must use ZRS"
  }
}
