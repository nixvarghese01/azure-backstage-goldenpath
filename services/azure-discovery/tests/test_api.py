from azure_discovery.inventory.base import AzurePermissionError, AzureThrottledError
from tests.conftest import AUTH, SUB


def test_requires_auth(client) -> None:
    assert client.get("/v1/subscriptions").status_code == 401


def test_lists_only_allowlisted_subscriptions(client) -> None:
    res = client.get("/v1/subscriptions", headers=AUTH)
    assert res.status_code == 200
    assert [s["id"] for s in res.json()] == [SUB]


def test_resource_groups_filtered_by_allowlist_and_region(client) -> None:
    res = client.get(f"/v1/subscriptions/{SUB}/resource-groups?environment=dev", headers=AUTH)
    assert [g["name"] for g in res.json()] == ["rg-sportify-apps-dev"]


def test_unknown_subscription_is_not_found(client) -> None:
    res = client.get("/v1/subscriptions/11111111-1111-1111-1111-111111111111/resource-groups", headers=AUTH)
    assert res.status_code == 404


def test_aks_clusters_report_ha_eligibility(client) -> None:
    res = client.get(f"/v1/subscriptions/{SUB}/aks-clusters", headers=AUTH)
    cluster = res.json()[0]
    assert cluster["name"] == "aks-sportify-shared-dev"
    assert cluster["ha_eligible"] is False


def test_storage_resources(client) -> None:
    res = client.get(f"/v1/subscriptions/{SUB}/resources?type=storage", headers=AUTH)
    assert [d["name"] for d in res.json()] == ["stsportifyshareddev"]


def test_capabilities_free_subscription(client) -> None:
    res = client.get(f"/v1/subscriptions/{SUB}/capabilities?region=uksouth", headers=AUTH)
    body = res.json()
    assert body["create_new"]["subscription"]["available"] is False
    assert "EA or MCA" in body["create_new"]["subscription"]["reason"]
    assert body["create_new"]["aks_cluster"]["available"] is True


def test_capabilities_low_quota_disables_new_cluster(client, inventory) -> None:
    inventory.vcpus = (4, 4)
    res = client.get(f"/v1/subscriptions/{SUB}/capabilities?region=uksouth", headers=AUTH)
    assert res.json()["create_new"]["aks_cluster"]["available"] is False


def test_permission_error_maps_to_403(client, inventory, monkeypatch) -> None:
    def boom(_sub: str):
        raise AzurePermissionError("no reader")

    monkeypatch.setattr(inventory, "list_resource_groups", boom)
    res = client.get(f"/v1/subscriptions/{SUB}/resource-groups", headers=AUTH)
    assert res.status_code == 403
    assert res.json()["code"] == "permission_denied"


def test_throttling_maps_to_503(client, inventory, monkeypatch) -> None:
    def boom(_sub: str):
        raise AzureThrottledError("429")

    monkeypatch.setattr(inventory, "list_aks_clusters", boom)
    res = client.get(f"/v1/subscriptions/{SUB}/aks-clusters", headers=AUTH)
    assert res.status_code == 503
    assert res.json()["code"] == "throttled"
