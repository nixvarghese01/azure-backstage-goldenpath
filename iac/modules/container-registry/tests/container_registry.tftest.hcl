mock_provider "azurerm" {}

variables {
  name                = "acrordersapidev"
  resource_group_name = "rg-idp-registry-dev"
  location            = "swedencentral"
  tags                = { "managed-by" = "idp-platform" }
}

run "no_admin_user_or_anonymous_pull" {
  command = plan
  assert {
    condition     = azurerm_container_registry.this.admin_enabled == false
    error_message = "the admin user must be off (Entra auth only)"
  }
  assert {
    condition     = azurerm_container_registry.this.anonymous_pull_enabled == false
    error_message = "anonymous pull must be off"
  }
  assert {
    condition     = azurerm_container_registry.this.sku == "Basic"
    error_message = "Basic is the default SKU"
  }
}

run "rejects_an_unknown_sku" {
  command = plan
  variables {
    sku = "Free"
  }
  expect_failures = [var.sku]
}

run "rejects_hyphens_in_the_name" {
  command = plan
  variables {
    name = "acr-orders"
  }
  expect_failures = [var.name]
}
