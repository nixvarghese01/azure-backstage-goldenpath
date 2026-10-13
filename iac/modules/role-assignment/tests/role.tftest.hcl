mock_provider "azurerm" {}

variables {
  scope        = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg"
  principal_id = "11111111-1111-1111-1111-111111111111"
}

run "allowed_role" {
  command = plan
  variables {
    role_definition_name = "Storage Blob Data Contributor"
  }
}

run "owner_is_rejected" {
  command = plan
  variables {
    role_definition_name = "Owner"
  }
  expect_failures = [terraform_data.role_allowed]
}
