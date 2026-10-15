mock_provider "azapi" {}

variables {
  name                = "sub-orders-api-dev"
  billing_scope       = "/providers/Microsoft.Billing/billingAccounts/1/enrollmentAccounts/2"
  management_group_id = "/providers/Microsoft.Management/managementGroups/corp"
  tags                = { "managed-by" = "idp-platform" }
}

run "devtest_alias_under_the_management_group" {
  command = plan
  assert {
    condition     = azapi_resource.alias.body.properties.workload == "DevTest"
    error_message = "subscriptions are DevTest unless asked otherwise"
  }
  assert {
    condition     = azapi_resource.alias.body.properties.additionalProperties.managementGroupId == "/providers/Microsoft.Management/managementGroups/corp"
    error_message = "the subscription must be placed in the given management group"
  }
}

run "rejects_a_non_billing_scope" {
  command = plan
  variables {
    billing_scope = "/subscriptions/00000000-0000-0000-0000-000000000000"
  }
  expect_failures = [var.billing_scope]
}

run "rejects_an_unknown_workload" {
  command = plan
  variables {
    workload = "Sandbox"
  }
  expect_failures = [var.workload]
}
