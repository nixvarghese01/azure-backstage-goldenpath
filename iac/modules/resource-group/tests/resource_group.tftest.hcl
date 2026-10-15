mock_provider "azurerm" {}

variables {
  name     = "rg-orders-api-dev"
  location = "swedencentral"
  tags     = { "workload" = "orders-api", "environment" = "dev", "owner" = "team-orders" }
}

run "creates_the_group_with_its_tags" {
  command = plan
  assert {
    condition     = azurerm_resource_group.this.name == "rg-orders-api-dev"
    error_message = "the group must keep the given name"
  }
  assert {
    condition     = azurerm_resource_group.this.tags["owner"] == "team-orders"
    error_message = "tags must be applied (landing zone policies require them)"
  }
}

run "rejects_a_name_without_the_rg_prefix" {
  command = plan
  variables {
    name = "orders-api-dev"
  }
  expect_failures = [var.name]
}
