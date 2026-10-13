from tests.conftest import AUTH, base_request


def _validate(client, **overrides) -> dict:
    res = client.post("/v1/validate", json=base_request(**overrides), headers=AUTH)
    assert res.status_code == 200
    return res.json()


def _codes(body: dict) -> set[str]:
    return {e["code"] for e in body["errors"]}


def test_golden_path_request_is_valid(client) -> None:
    body = _validate(client)
    assert body["valid"] is True, body["errors"]
    assert body["platform_changes"] == []
    assert "aks_cluster_id" in body["resolved"]


def test_demo_stack_rejects_unsupported_azure_capability(client, policy) -> None:
    stack = next(item for item in policy.stacks if item.id == "fastapi")
    stack.enabled = True
    assert "stack_capability_not_supported" in _codes(_validate(client, stack="fastapi"))
    body = _validate(client, stack="fastapi", runtime_capability={"type": "none", "mode": "existing"})
    assert body["valid"] is True, body["errors"]


def test_tampered_resource_group_is_rejected(client) -> None:
    body = _validate(client, resource_group={"mode": "existing", "name": "rg-other"})
    assert "not_allowlisted" in _codes(body)


def test_subscription_not_allowlisted(client) -> None:
    body = _validate(client, subscription={"mode": "existing", "id": "11111111-1111-1111-1111-111111111111"})
    assert "not_allowlisted" in _codes(body)


def test_new_subscription_unavailable_without_billing_scope(client) -> None:
    body = _validate(
        client,
        subscription={"mode": "new", "name": "sub-new"},
        resource_group={"mode": "new", "name": "rg-new-app"},
        aks_cluster={"mode": "new", "name": "aks-new"},
        container_registry={"mode": "new", "name": "acrnewapp"},
    )
    assert "capability_unavailable" in _codes(body)
    assert "subscription" in body["platform_changes"]


def test_invalid_application_name(client) -> None:
    assert "invalid_name" in _codes(_validate(client, application_name="Bad_Name"))


def test_reserved_namespace(client) -> None:
    assert "invalid_name" in _codes(_validate(client, namespace={"mode": "new", "name": "kube-system"}))


def test_ha_requires_justification_in_dev(client) -> None:
    body = _validate(client, availability={"tier": "ha"})
    assert {"reason_required", "justification_required"} <= _codes(body)


def test_ha_rejects_placeholder_justification(client) -> None:
    body = _validate(client, availability={"tier": "ha", "reason": "customer-facing", "justification": "n/a"})
    assert "justification_required" in _codes(body)


def test_ha_rejected_on_non_zonal_cluster_with_lrs_warning(client) -> None:
    body = _validate(
        client,
        availability={
            "tier": "ha",
            "reason": "customer-facing",
            "slo_target": "99.9",
            "justification": "Public checkout API used by the web shop; outages block orders.",
        },
    )
    assert "cluster_not_zonal" in _codes(body)
    assert "ha_with_lrs" in {w["code"] for w in body["warnings"]}


def test_ha_accepted_on_zonal_cluster(client, inventory) -> None:
    pool = inventory.clusters[0].node_pools[0]
    pool.count, pool.zones = 3, ["1", "2", "3"]
    body = _validate(
        client,
        availability={
            "tier": "ha",
            "reason": "customer-facing",
            "slo_target": "99.9",
            "justification": "Public checkout API used by the web shop; outages block orders.",
        },
    )
    assert "cluster_not_zonal" not in _codes(body)


def test_new_aks_cluster_blocked_by_quota(client, inventory) -> None:
    inventory.vcpus = (4, 4)
    body = _validate(client, aks_cluster={"mode": "new", "name": "aks-orders-dev"})
    assert "capability_unavailable" in _codes(body)
    assert "aks_cluster" in body["platform_changes"]


def test_disabled_stack_rejected(client) -> None:
    assert "stack_not_available" in _codes(_validate(client, stack="fastapi"))
