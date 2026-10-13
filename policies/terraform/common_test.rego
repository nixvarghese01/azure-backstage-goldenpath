package main_test

import rego.v1

import data.main

tags := {"managed-by": "sportify-platform", "environment": "dev", "owner": "team-orders", "application": "orders-api", "lifecycle": "application"}

allow_data := {"regions": ["uksouth"], "skus": {"storage_account": ["Standard_LRS", "Standard_ZRS"]}}

storage(after) := {"resource_changes": [{"address": "module.storage.azurerm_storage_account.this", "type": "azurerm_storage_account", "change": {"actions": ["create"], "before": null, "after": after}}]}

good_storage := {"location": "uksouth", "tags": tags, "shared_access_key_enabled": false, "allow_nested_items_to_be_public": false, "account_tier": "Standard", "account_replication_type": "LRS"}

test_compliant_storage_passes if {
	count(main.deny) == 0 with input as storage(good_storage) with data.regions as allow_data.regions with data.skus as allow_data.skus
}

test_wrong_region_denied if {
	some msg in main.deny with input as storage(object.union(good_storage, {"location": "eastus"})) with data.regions as allow_data.regions with data.skus as allow_data.skus
	contains(msg, "region")
}

# object.union merges nested objects, so the tags are removed before being replaced.
test_missing_tags_denied if {
	some msg in main.deny with input as storage(object.union(object.remove(good_storage, ["tags"]), {"tags": {"owner": "x"}})) with data.regions as allow_data.regions with data.skus as allow_data.skus
	contains(msg, "missing required tags")
}

test_shared_keys_denied if {
	some msg in main.deny with input as storage(object.union(good_storage, {"shared_access_key_enabled": true})) with data.regions as allow_data.regions with data.skus as allow_data.skus
	contains(msg, "shared access keys")
}

test_unmanaged_update_denied if {
	inp := {"resource_changes": [{"address": "azurerm_storage_account.existing", "type": "azurerm_storage_account", "change": {"actions": ["update"], "before": {"tags": {"owner": "someone"}}, "after": good_storage}}]}
	some msg in main.deny with input as inp with data.regions as allow_data.regions with data.skus as allow_data.skus
	contains(msg, "not managed by sportify-platform")
}
