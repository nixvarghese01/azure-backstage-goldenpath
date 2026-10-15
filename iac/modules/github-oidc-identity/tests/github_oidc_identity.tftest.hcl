mock_provider "azurerm" {}

variables {
  name                = "id-idp-platform-dev"
  resource_group_name = "rg-idp-identities-dev"
  location            = "swedencentral"
  subjects = {
    "github-platform" = "repo:org@1/repo@2:environment:platform"
  }
  tags = { "managed-by" = "idp-platform" }
}

run "federates_github_environments_without_secrets" {
  command = plan
  assert {
    condition     = azurerm_federated_identity_credential.github["github-platform"].issuer == "https://token.actions.githubusercontent.com"
    error_message = "the issuer must be GitHub Actions"
  }
  assert {
    condition     = azurerm_federated_identity_credential.github["github-platform"].subject == "repo:org@1/repo@2:environment:platform"
    error_message = "the subject must be passed through unchanged (immutable IDs)"
  }
  assert {
    condition     = tolist(azurerm_federated_identity_credential.github["github-platform"].audience) == tolist(["api://AzureADTokenExchange"])
    error_message = "the audience must be the Entra token exchange"
  }
}

run "rejects_more_than_20_credentials" {
  command = plan
  variables {
    subjects = { for i in range(21) : "c${i}" => "repo:org/repo:environment:e${i}" }
  }
  expect_failures = [var.subjects]
}
