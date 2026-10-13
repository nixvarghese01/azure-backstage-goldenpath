variables {
  application = "orders-api"
  environment = "dev"
  owner       = "team-orders"
  request_id  = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
}

run "tags_and_names" {
  command = plan

  assert {
    condition     = output.tags["managed-by"] == "idp-platform" && output.tags["request-id"] != ""
    error_message = "standard tags missing"
  }
  assert {
    condition     = output.names.storage_account == "stordersapidev"
    error_message = "storage account name must be compact and lowercase"
  }
  assert {
    condition     = length(output.names.key_vault) <= 24
    error_message = "key vault name too long"
  }
}

run "rejects_bad_application_name" {
  command = plan
  variables {
    application = "Bad_Name"
  }
  expect_failures = [var.application]
}
