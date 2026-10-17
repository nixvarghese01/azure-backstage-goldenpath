package app_test

import rego.v1

import data.app

rc(type, after) := {"resource_changes": [{"address": sprintf("x.%s", [type]), "type": type, "change": {"actions": ["create"], "after": after}}]}

test_role_allowlist if {
	count(app.deny) == 0 with input as rc("azurerm_role_assignment", {"role_definition_name": "Storage Blob Data Contributor"}) with data.roles.assignable as ["Storage Blob Data Contributor"]
}

test_owner_role_denied if {
	some msg in app.deny with input as rc("azurerm_role_assignment", {"role_definition_name": "Owner"}) with data.roles.assignable as ["Storage Blob Data Contributor"]
	contains(msg, "not assignable")
}

test_compute_denied_in_app_repo if {
	some msg in app.deny with input as rc("azurerm_linux_virtual_machine", {}) with data.roles.assignable as []
	contains(msg, "not allowed")
}

test_only_deployer_role_binding if {
	some msg in app.deny with input as rc("kubernetes_role_binding_v1", {"role_ref": [{"name": "cluster-admin"}]}) with data.roles.assignable as []
	contains(msg, "idp-app-deployer")
}
