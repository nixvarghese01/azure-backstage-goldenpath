variables {
  application = "orders-api"
  environment = "dev"
  owner       = "team-orders"
  request_id  = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
}

run "tags_and_names" {
  command = plan

  assert {
    condition     = output.tags["managed-by"] == "idp-platform" && output.tags["request-id"] != "" && output.tags["workload"] == var.application
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

run "extra_tags_add_but_never_override" {
  command = plan

  variables {
    extra_tags = { costCenter = "cc-1234", owner = "someone-else" }
  }

  assert {
    condition     = output.tags["costCenter"] == "cc-1234" && output.tags["owner"] == "team-orders"
    error_message = "organisation tags must be added without overriding the standard tags"
  }
}
