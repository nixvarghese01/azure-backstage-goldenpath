# Plan policies for every stack (platform and application).
# Run: conftest test plan.json -p policies/terraform -d policies/allowlist.yaml --namespace main
# Input: `terraform show -json <plan>`. Data: policies/allowlist.yaml (loaded at the data root).
package main

import rego.v1

required_tags := {"managed-by", "environment", "owner", "application", "lifecycle"}

changes contains rc if {
	some rc in input.resource_changes
	not "no-op" in rc.change.actions
	not "read" in rc.change.actions
}

creates_or_updates(rc) if "create" in rc.change.actions

creates_or_updates(rc) if "update" in rc.change.actions

deny contains msg if {
	some rc in changes
	creates_or_updates(rc)
	loc := lower(rc.change.after.location)
	not loc in {lower(r) | some r in data.regions}
	msg := sprintf("%s: region '%s' is not on the allowlist", [rc.address, loc])
}

deny contains msg if {
	some rc in changes
	creates_or_updates(rc)
	is_object(rc.change.after.tags)
	missing := required_tags - {k | some k, _ in rc.change.after.tags}
	count(missing) > 0
	msg := sprintf("%s: missing required tags %v", [rc.address, sort(missing)])
}

# The platform never changes or destroys resources it didn't create.
deny contains msg if {
	some rc in changes
	some action in rc.change.actions
	action in {"update", "delete"}
	is_object(rc.change.before.tags)
	object.get(rc.change.before.tags, "managed-by", "") != "idp-platform"
	msg := sprintf("%s: %s of a resource not managed by idp-platform", [rc.address, action])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_storage_account"
	creates_or_updates(rc)
	rc.change.after.shared_access_key_enabled == true
	msg := sprintf("%s: shared access keys must be disabled", [rc.address])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_storage_account"
	creates_or_updates(rc)
	rc.change.after.allow_nested_items_to_be_public == true
	msg := sprintf("%s: public blob access is not allowed", [rc.address])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_storage_account"
	creates_or_updates(rc)
	sku := sprintf("%s_%s", [rc.change.after.account_tier, rc.change.after.account_replication_type])
	not sku in data.skus.storage_account
	msg := sprintf("%s: storage SKU %s is not allowlisted", [rc.address, sku])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_container_registry"
	creates_or_updates(rc)
	rc.change.after.admin_enabled == true
	msg := sprintf("%s: the ACR admin user must stay disabled", [rc.address])
}
