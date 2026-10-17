# Extra rules for application repositories (not platform stacks).
# Run: conftest test plan.json -p policies/terraform -d policies/allowlist.yaml --namespace main --namespace app
package app

import rego.v1

allowed_types := {
	"azurerm_resource_group",
	"azurerm_user_assigned_identity",
	"azurerm_federated_identity_credential",
	"azurerm_storage_account",
	"azurerm_storage_container",
	"azurerm_key_vault",
	"azurerm_role_assignment",
	"kubernetes_namespace_v1",
	"kubernetes_resource_quota_v1",
	"kubernetes_limit_range_v1",
	"kubernetes_role_binding_v1",
	"terraform_data",
}

changes contains rc if {
	some rc in input.resource_changes
	not "no-op" in rc.change.actions
	not "read" in rc.change.actions
}

deny contains msg if {
	some rc in changes
	not rc.type in allowed_types
	msg := sprintf("%s: resource type %s is not allowed in application repositories", [rc.address, rc.type])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_role_assignment"
	"create" in rc.change.actions
	not rc.change.after.role_definition_name in data.roles.assignable
	msg := sprintf("%s: role '%s' is not assignable by the platform", [rc.address, rc.change.after.role_definition_name])
}

deny contains msg if {
	some rc in changes
	rc.type == "kubernetes_role_binding_v1"
	"create" in rc.change.actions
	some ref in rc.change.after.role_ref
	ref.name != "idp-app-deployer"
	msg := sprintf("%s: only the idp-app-deployer ClusterRole may be bound", [rc.address])
}
