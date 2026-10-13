# Non-sensitive outputs reported to the orchestrator and used to fill the application's Helm values.

output "identity_client_id" {
  description = "ServiceAccount annotation azure.workload.identity/client-id."
  value       = module.runtime_identity.client_id
}

output "namespace" {
  value = var.namespace.name
}

output "service_account" {
  value = module.naming.names.service_account
}

output "resource_group_name" {
  value = local.rg_name
}

output "acr_login_server" {
  value = data.azurerm_container_registry.shared.login_server
}

output "storage_account_name" {
  value = local.storage_name
}

output "key_vault_uri" {
  value = local.vault_uri
}
