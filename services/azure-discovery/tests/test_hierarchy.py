"""Tenant -> management group -> subscription discovery (Cloud Adoption Framework landing zones)."""

from azure_discovery.inventory.mock import TENANT

from tests.conftest import AUTH, SUB
from tests.test_validation import _codes, _validate


def test_tenants_list_only_the_approved_tenant(client) -> None:
    res = client.get("/v1/tenants?environment=dev", headers=AUTH)
    assert res.status_code == 200
    assert [t["id"] for t in res.json()] == [TENANT]


def test_management_groups_are_pruned_to_the_approved_landing_zone(client) -> None:
    res = client.get(f"/v1/management-groups?tenant_id={TENANT}&environment=dev", headers=AUTH)
    assert res.status_code == 200
    groups = res.json()
    # Depth-first from the Tenant Root Group; Platform, Sandbox and Decommissioned hold no approved
    # application subscription, so they are left out.
    assert [g["id"] for g in groups] == [TENANT, "xycorp", "xycorp-landingzones", "xycorp-corp"]
    assert groups[-1]["path"] == ["Tenant Root Group", "XY Corp", "Landing zones", "Corp"]
    assert groups[-1]["depth"] == 3


def test_management_groups_fall_back_to_the_tenant_root(client, inventory) -> None:
    # A free-tier tenant, or an identity without management group Reader access.
    inventory.management_groups = []
    res = client.get(f"/v1/management-groups?tenant_id={TENANT}", headers=AUTH)
    assert [(g["id"], g["name"]) for g in res.json()] == [(TENANT, "Tenant Root Group")]


def test_subscriptions_filtered_by_management_group_subtree(client) -> None:
    def ids(mg: str) -> list[str]:
        res = client.get(f"/v1/subscriptions?tenant_id={TENANT}&management_group={mg}", headers=AUTH)
        return [s["id"] for s in res.json()]

    assert ids("xycorp-corp") == [SUB]
    assert ids("xycorp-landingzones") == [SUB]
    assert ids(TENANT) == [SUB]  # the Tenant Root Group contains everything
    assert ids("xycorp-online") == []


def test_subscription_outside_the_landing_zones_is_hidden(client, inventory) -> None:
    inventory.subscriptions[0].management_groups = ["xycorp-sandbox", "xycorp", TENANT]
    assert client.get("/v1/subscriptions", headers=AUTH).json() == []
    assert "outside_landing_zone" in _codes(_validate(client))


def test_no_hierarchy_policy_accepts_a_subscription_under_the_root(client, inventory, policy) -> None:
    policy.hierarchy.tenant_id = None
    policy.hierarchy.application_management_groups = []
    inventory.subscriptions[0].management_groups = []
    assert [s["id"] for s in client.get("/v1/subscriptions", headers=AUTH).json()] == [SUB]
    assert _validate(client)["valid"] is True


def test_validation_checks_the_selected_management_group(client) -> None:
    assert _validate(client, tenant_id=TENANT, management_group="xycorp-corp")["valid"] is True
    assert "not_in_management_group" in _codes(_validate(client, management_group="xycorp-online"))


def test_validation_rejects_another_tenant(client) -> None:
    other = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert "wrong_tenant" in _codes(_validate(client, tenant_id=other))


def test_data_resources_filtered_by_resource_group(client) -> None:
    def names(rg: str) -> list[str]:
        url = f"/v1/subscriptions/{SUB}/resources?type=storage&resource_group={rg}"
        return [d["name"] for d in client.get(url, headers=AUTH).json()]

    assert names("rg-idp-apps-dev") == ["stidpshareddev"]
    assert names("rg-orders-api-dev") == []
