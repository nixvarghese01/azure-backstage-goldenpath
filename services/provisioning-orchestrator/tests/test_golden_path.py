"""End-to-end golden path with mocked GitHub and discovery: submit -> ... -> SUCCEEDED."""

from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.models import Request

from tests.conftest import APPROVER, REQUESTER, SERVICE, callback, drain, submission, webhook

PLAN_HASH = "a" * 64


def _get(client, rid: str) -> dict:
    return client.get(f"/v1/requests/{rid}", headers=SERVICE).json()


def _to_awaiting_approval(client, worker, github) -> str:
    rid = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    drain(worker)
    assert _get(client, rid)["ready_for_repository"] is True
    res = client.post(
        f"/v1/requests/{rid}/repository",
        headers=SERVICE,
        json={
            "owner": "nixvarghese01",
            "name": "orders-api",
            "url": "https://github.com/nixvarghese01/orders-api",
        },
    )
    assert res.json()["state"] == "REPOSITORY_CREATED"
    drain(worker)
    assert (
        "dispatch",
        {
            "repo": "orders-api",
            "workflow": "terraform-validate.yml",
            "ref": "main",
            "inputs": {"request_id": rid},
        },
    ) in github.calls
    callback(client, rid, "validate", "success", 1)
    drain(worker)
    callback(
        client,
        rid,
        "plan",
        "success",
        2,
        {"plan_hash": PLAN_HASH, "summary": {"add": 7, "change": 0, "destroy": 0}},
    )
    drain(worker)
    assert _get(client, rid)["state"] == "INFRASTRUCTURE_PLANNED"
    webhook(
        client,
        "deployment_protection_rule",
        f"dpr-{rid}",
        {
            "action": "requested",
            "environment": "dev-infra",
            "deployment_callback_url": "https://api.github.com/callback/1",
            "repository": {"name": "orders-api"},
        },
    )
    drain(worker)
    assert _get(client, rid)["state"] == "AWAITING_APPROVAL"
    return rid


def test_golden_path_reaches_succeeded(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)

    res = client.post(
        f"/v1/requests/{rid}/approval",
        headers=APPROVER,
        json={"decision": "approve", "plan_hash": PLAN_HASH, "comment": "LGTM"},
    )
    assert res.json()["state"] == "PROVISIONING"
    drain(worker)
    assert any(c[0] == "review" and c[1]["approve"] for c in github.calls)

    callback(
        client,
        rid,
        "apply",
        "success",
        3,
        {"outputs": {"identity_client_id": "abc", "namespace": "orders-api"}},
    )
    drain(worker)
    body = _get(client, rid)
    assert body["state"] == "APPLICATION_BUILDING"
    assert body["application"]["pr_number"] == 1

    webhook(
        client,
        "workflow_run",
        f"wr-{rid}",
        {
            "action": "completed",
            "repository": {"name": "orders-api"},
            "workflow_run": {
                "id": 9,
                "conclusion": "success",
                "event": "pull_request",
                "head_branch": f"idp/app-{rid}",
                "name": "application-ci",
            },
        },
    )
    drain(worker)
    assert any(c[0] == "merge" for c in github.calls)

    callback(client, rid, "ci", "success", 4, {"image": "acridpdev.azurecr.io/orders-api:abc123"})
    callback(client, rid, "deploy", "started", 5)
    callback(client, rid, "deploy", "success", 5, {"endpoint": "orders-api.dev.xycorp.local", "pods": "1/1"})
    drain(worker)

    body = _get(client, rid)
    assert body["state"] == "SUCCEEDED"
    assert [o["status"] for o in body["outcomes"]] == ["succeeded"] * 5
    assert body["urls"]["application"] == "https://orders-api.dev.xycorp.local"
    assert body["urls"]["api_docs"].endswith("/docs")


def test_replayed_callback_is_ignored(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    # Same run + stage + status again: deduplicated, state unchanged.
    res = client.post(
        "/v1/callbacks/actions",
        headers=SERVICE,
        json={
            "request_id": rid,
            "stage": "plan",
            "status": "success",
            "run_id": 2,
            "data": {"plan_hash": PLAN_HASH},
        },
    )
    assert res.json()["status"] == "duplicate"
    assert _get(client, rid)["state"] == "AWAITING_APPROVAL"


def test_requester_cannot_approve_own_request(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    headers = {**REQUESTER, "X-IDP-Groups": "group:default/team-orders,group:default/platform-approvers"}
    res = client.post(
        f"/v1/requests/{rid}/approval", headers=headers, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "separation_of_duties"


def test_self_approval_is_off_by_default_and_never_prod(monkeypatch) -> None:
    monkeypatch.delenv("ORCHESTRATOR_SELF_APPROVAL_ENVIRONMENTS", raising=False)
    assert Settings.from_env().self_approval_environments == frozenset()
    monkeypatch.setenv("ORCHESTRATOR_SELF_APPROVAL_ENVIRONMENTS", "dev, prod")
    assert Settings.from_env().self_approval_environments == frozenset({"dev"})


def test_self_approval_allowed_when_dev_opts_in(client_factory, worker, github) -> None:
    client = client_factory(self_approval_environments=frozenset({"dev"}))
    rid = _to_awaiting_approval(client, worker, github)
    headers = {**REQUESTER, "X-IDP-Groups": "group:default/team-orders,group:default/platform-approvers"}
    res = client.post(
        f"/v1/requests/{rid}/approval", headers=headers, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    assert res.status_code == 200, res.json()
    assert res.json()["approval"]["self_approved"] is True


def test_approval_bound_to_plan_hash(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    res = client.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": "b" * 64}
    )
    assert res.json()["detail"]["code"] == "plan_changed"


def test_double_approval_applies_once(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    ok = client.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    again = client.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    assert ok.status_code == 200 and again.status_code == 409
    drain(worker)
    assert sum(1 for c in github.calls if c[0] == "review") == 1


def test_reject_cancels_and_rejects_rule(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    res = client.post(
        f"/v1/requests/{rid}/approval",
        headers=APPROVER,
        json={"decision": "reject", "plan_hash": PLAN_HASH, "comment": "too big"},
    )
    assert res.json()["state"] == "CANCELLED"
    drain(worker)
    assert any(c[0] == "review" and not c[1]["approve"] for c in github.calls)


def test_validation_failure_fails_before_repository(client, worker, discovery) -> None:
    discovery.result = {
        "valid": False,
        "errors": [{"field": "resource_group", "code": "not_allowlisted", "message": "not approved"}],
        "warnings": [],
        "platform_changes": [],
        "resolved": {},
    }
    rid = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    drain(worker)
    body = _get(client, rid)
    assert body["state"] == "FAILED"
    assert body["error"]["stage"] == "validate"
    assert body["repository"] == {}


def test_deploy_failure_is_not_success(client, worker, github) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    client.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    drain(worker)
    callback(client, rid, "apply", "success", 3, {"outputs": {}})
    drain(worker)
    callback(client, rid, "deploy", "failure", 6, {"message": "rollout timed out"})
    drain(worker)
    body = _get(client, rid)
    assert body["state"] == "FAILED"
    statuses = {o["name"]: o["status"] for o in body["outcomes"]}
    assert statuses["Repository created"] == "succeeded"
    assert statuses["Deployed"] == "failed"


def test_platform_resources_go_through_platform_pr(client, worker, github, discovery) -> None:
    discovery.result = {**discovery.result, "platform_changes": ["aks_cluster"]}
    rid = client.post(
        "/v1/requests",
        json=submission(aks_cluster={"mode": "new", "name": "aks-orders-dev"}),
        headers=REQUESTER,
    ).json()["id"]
    drain(worker)
    body = _get(client, rid)
    assert body["state"] == "PLATFORM_PROVISIONING"
    assert body["ready_for_repository"] is False
    commit = next(c for c in github.calls if c[0] == "commit")
    assert commit[1]["files"] == ["iac/platform/20-shared-dev/clusters.d/aks-orders-dev.json"]
    webhook(
        client,
        "pull_request",
        f"pr-{rid}",
        {
            "action": "closed",
            "repository": {"name": "azure-backstage-goldenpath"},
            "pull_request": {"merged": True, "head": {"ref": f"idp/platform-{rid}"}},
        },
    )
    drain(worker)
    assert any(c[0] == "dispatch" and c[1]["workflow"] == "platform-apply.yml" for c in github.calls)
    callback(client, rid, "platform_apply", "success", 11)
    drain(worker)
    assert _get(client, rid)["ready_for_repository"] is True


def test_cleanup_destroys_with_approval_and_unregisters(client, worker, github, ctx) -> None:
    rid = _to_awaiting_approval(client, worker, github)
    client.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    drain(worker)
    callback(client, rid, "apply", "success", 3, {"outputs": {"identity_client_id": "x"}})
    drain(worker)
    callback(client, rid, "ci", "success", 4, {"image": "acr/orders-api:1"})
    callback(client, rid, "deploy", "started", 5)
    callback(client, rid, "deploy", "success", 5, {"endpoint": "orders-api.dev.xycorp.local"})
    drain(worker)
    assert _get(client, rid)["state"] == "SUCCEEDED"

    # Cleanup: uninstall -> destroy plan -> approval (held rule) -> destroy apply -> CLEANED_UP.
    res = client.post(f"/v1/requests/{rid}/cleanup", headers=REQUESTER)
    assert res.json()["state"] == "CLEANUP_PENDING"
    drain(worker)
    assert any(c[0] == "dispatch" and c[1]["inputs"].get("action") == "uninstall" for c in github.calls)
    callback(client, rid, "uninstall", "success", 6)
    drain(worker)
    destroy_hash = "d" * 64
    callback(client, rid, "plan", "success", 7, {"plan_hash": destroy_hash, "summary": {"destroy": 7}})
    drain(worker)
    webhook(
        client,
        "deployment_protection_rule",
        f"dpr-destroy-{rid}",
        {
            "action": "requested",
            "environment": "dev-infra",
            "deployment_callback_url": "https://api.github.com/callback/2",
            "repository": {"name": "orders-api"},
        },
    )
    drain(worker)
    assert _get(client, rid)["cleanup"]["stage"] == "awaiting_approval"
    ok = client.post(
        f"/v1/requests/{rid}/approval",
        headers=APPROVER,
        json={"decision": "approve", "plan_hash": destroy_hash},
    )
    assert ok.status_code == 200, ok.text
    drain(worker)
    callback(client, rid, "apply", "success", 8)
    drain(worker)
    assert _get(client, rid)["state"] == "CLEANED_UP"
    assert {"unregistered": "component:default/orders-api"} in ctx.backstage.sent


def test_empty_endpoint_host_takes_the_validated_default(client, worker, discovery, ctx) -> None:
    discovery.result = {**discovery.result, "resolved": {"endpoint_host": "orders-api.dev.xycorp.local"}}
    rid = client.post("/v1/requests", json=submission(endpoint_host=""), headers=REQUESTER).json()["id"]
    drain(worker)
    assert discovery.calls[0]["endpoint_host"] == ""
    with ctx.sessions() as s:
        assert s.get(Request, rid).spec["endpoint_host"] == "orders-api.dev.xycorp.local"
    assert _get(client, rid)["endpoint_host"] == "orders-api.dev.xycorp.local"
