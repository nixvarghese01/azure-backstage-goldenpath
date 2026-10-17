mock_provider "azurerm" {}

variables {
  name                = "id-orders-api-dev"
  resource_group_name = "rg-idp-apps-dev"
  location            = "uksouth"
  oidc_issuer_url     = "https://uksouth.oic.prod-aks.azure.com/tenant/cluster/"
  namespace           = "orders-api"
  service_account     = "orders-api"
  tags                = { "managed-by" = "idp-platform" }
}

run "federated_subject_matches_service_account" {
  command = plan
  assert {
    condition     = azurerm_federated_identity_credential.workload.subject == "system:serviceaccount:orders-api:orders-api"
    error_message = "subject must bind to the app's service account"
  }
}

run "rejects_plain_http_issuer" {
  command = plan
  variables {
    oidc_issuer_url = "http://insecure"
  }
  expect_failures = [var.oidc_issuer_url]
}
