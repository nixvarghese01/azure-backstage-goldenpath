"""Golden path across services with mocked Azure and GitHub: Backstage-shaped submission -> validation in
the real discovery service -> repository -> plan -> approval -> apply -> application PR rendered from
the real NestJS template -> CI -> deploy -> SUCCEEDED with shared URLs."""

from __future__ import annotations

import pytest

from e2e.conftest import AUTH

SUB = "00000000-0000-0000-0000-000000000000"
PLAN_HASH = "c" * 64
REQUESTER = {**AUTH, "X-Sportify-User": "user:default/alex", "X-Sportify-Groups": "group:default/team-orders"}
APPROVER = {
    **AUTH,
    "X-Sportify-User": "user:default/sam",
    "X-Sportify-Groups": "group:default/platform-approvers",
}


def submission(**overrides):
    body = {
        "idempotency_key": "scaffolder-e2e-0001",
        "application_name": "orders-api",
        "description": "Order management REST API",
        "owner": "group:default/team-orders",
        "environment": "dev",
        "region": "uksouth",
        "stack": "nestjs",
        "subscription": {"mode": "existing", "id": SUB},
        "resource_group": {"mode": "existing", "name": "rg-sportify-apps-dev"},
        "aks_cluster": {"mode": "existing", "name": "aks-sportify-shared-dev"},
        "container_registry": {"mode": "existing", "name": "acrsportifydev"},
        "namespace": {"mode": "new", "name": "orders-api"},
        "runtime_capability": {"type": "storage", "mode": "existing", "name": "stsportifyshareddev"},
        "availability": {"tier": "standard"},
        "endpoint_host": "orders-api.dev.sportify.example",
    }
    body.update(overrides)
    return body


def drain(worker, rounds: int = 30) -> None:
    for _ in range(rounds):
        progressed = worker.process_inbox() > 0
        progressed = worker.run_one_step() or progressed
        worker.deliver_outbox()
        if not progressed:
            return


def callback(api, rid, stage, status, run_id, data=None):
    res = api.post(
        "/v1/callbacks/actions",
        headers=AUTH,
        json={
            "request_id": rid,
            "stage": stage,
            "status": status,
            "run_id": run_id,
            "run_url": f"https://github.com/sportify-org/orders-api/actions/runs/{run_id}",
            "data": data or {},
        },
    )
    assert res.status_code == 202, res.text


def webhook(api, event, delivery, payload):
    import hashlib
    import hmac
    import json

    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"e2e-webhook-secret", body, hashlib.sha256).hexdigest()
    res = api.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202, res.text


def get(api, rid):
    return api.get(f"/v1/requests/{rid}", headers=AUTH).json()


@pytest.mark.parametrize(
    "stack, entrypoint",
    [
        ("nestjs", "src/main.ts"),
        ("fastapi", "app/main.py"),
        ("go", "main.go"),
        ("dotnet", "StarterApi.cs"),
        ("springboot", "src/main/java/com/sportify/starter/Starter.java"),
        ("nextjs", "app/page.jsx"),
        ("react", "src/App.tsx"),
        ("vue", "src/App.vue"),
    ],
)
def test_golden_path_end_to_end(system, discovery, stack, entrypoint) -> None:
    api, worker, github = system["api"], system["worker"], system["github"]

    # Enabling an unvalidated stack here is confined to this in-process test policy.
    next(item for item in discovery.app.state.policy.stacks if item.id == stack).enabled = True
    body = submission(stack=stack)
    if stack != "nestjs":
        body["runtime_capability"] = {"type": "none", "mode": "existing"}
    rid = api.post("/v1/requests", json=body, headers=REQUESTER).json()["id"]
    drain(worker)
    body = get(api, rid)
    assert body["ready_for_repository"] is True, body["validation"]

    api.post(
        f"/v1/requests/{rid}/repository",
        headers=AUTH,
        json={
            "owner": "sportify-org",
            "name": "orders-api",
            "url": "https://github.com/sportify-org/orders-api",
        },
    )
    drain(worker)
    callback(api, rid, "validate", "success", 1)
    drain(worker)
    callback(
        api,
        rid,
        "plan",
        "success",
        2,
        {"plan_hash": PLAN_HASH, "summary": {"add": 7, "change": 0, "destroy": 0}},
    )
    drain(worker)
    webhook(
        api,
        "deployment_protection_rule",
        "dpr-1",
        {
            "action": "requested",
            "environment": "dev-infra",
            "repository": {"name": "orders-api"},
            "deployment_callback_url": "https://api.github.com/repos/sportify-org/orders-api/actions/runs/3/deployment_protection_rule",
        },
    )
    drain(worker)
    assert get(api, rid)["state"] == "AWAITING_APPROVAL"
    assert any(n["title"].startswith("Approval needed") for n in system["backstage"].sent)

    api.post(
        f"/v1/requests/{rid}/approval", headers=APPROVER, json={"decision": "approve", "plan_hash": PLAN_HASH}
    )
    drain(worker)
    callback(
        api,
        rid,
        "apply",
        "success",
        3,
        {
            "outputs": {
                "identity_client_id": "11111111-2222-3333-4444-555555555555",
                "namespace": "orders-api",
                "acr_login_server": "acrsportifydev.azurecr.io",
                "storage_account_name": "stsportifyshareddev",
            }
        },
    )
    drain(worker)

    # The application PR is rendered from the real stack template with the real outputs.
    files = github.files[f"sportify/app-{rid}"]
    for expected in (
        entrypoint,
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        ".gitignore",
        "deploy/helm/application/values-dev.yaml",
        ".github/workflows/application-ci.yml",
        ".github/workflows/application-deploy.yml",
    ):
        assert expected in files, expected
    if stack in {"nestjs", "nextjs", "react", "vue"}:
        assert "package.json" in files
    assert "image: orders-api:local" in files["docker-compose.yml"]
    assert "orders-api" in files["Dockerfile"]
    values = files["deploy/helm/application/values-dev.yaml"]
    assert "11111111-2222-3333-4444-555555555555" in values
    assert "acrsportifydev.azurecr.io/orders-api" in values
    assert "host: orders-api.dev.sportify.example" in values
    assert "[[" not in "".join(files.values()), "unrendered template expression"

    webhook(
        api,
        "workflow_run",
        "wr-1",
        {
            "action": "completed",
            "repository": {"name": "orders-api"},
            "workflow_run": {
                "id": 9,
                "conclusion": "success",
                "event": "pull_request",
                "head_branch": f"sportify/app-{rid}",
                "name": "application-ci",
            },
        },
    )
    drain(worker)
    callback(api, rid, "ci", "success", 4, {"image": "acrsportifydev.azurecr.io/orders-api:abc"})
    callback(api, rid, "deploy", "started", 5)
    callback(api, rid, "deploy", "success", 5, {"endpoint": "orders-api.dev.sportify.example", "pods": "1/1"})
    drain(worker)

    final = get(api, rid)
    assert final["state"] == "SUCCEEDED"
    assert {o["name"]: o["status"] for o in final["outcomes"]} == {
        "Request validated": "succeeded",
        "Repository created": "succeeded",
        "Infrastructure provisioned": "succeeded",
        "Application built": "succeeded",
        "Deployed": "succeeded",
    }
    assert final["urls"]["application"] == "https://orders-api.dev.sportify.example"
    assert final["urls"]["azure_resource_group"].startswith(
        "https://portal.azure.com/#resource/subscriptions/"
    )
    assert any(n["title"].startswith("Deployed") for n in system["backstage"].sent)


def test_tampered_selection_is_rejected_before_repository(system) -> None:
    api, worker = system["api"], system["worker"]
    rid = api.post(
        "/v1/requests",
        json=submission(
            idempotency_key="scaffolder-e2e-0002", resource_group={"mode": "existing", "name": "rg-other"}
        ),
        headers=REQUESTER,
    ).json()["id"]
    drain(worker)
    body = get(api, rid)
    assert body["state"] == "FAILED"
    assert body["repository"] == {}
    assert any(e["code"] == "not_allowlisted" for e in body["validation"]["errors"])


def test_ha_on_non_zonal_cluster_is_rejected(system) -> None:
    api, worker = system["api"], system["worker"]
    rid = api.post(
        "/v1/requests",
        json=submission(
            idempotency_key="scaffolder-e2e-0003",
            availability={
                "tier": "ha",
                "reason": "customer-facing",
                "slo_target": "99.9",
                "justification": "Public checkout API; outages block orders and revenue.",
            },
        ),
        headers=REQUESTER,
    ).json()["id"]
    drain(worker)
    body = get(api, rid)
    assert body["state"] == "FAILED"
    assert any(e["code"] == "cluster_not_zonal" for e in body["validation"]["errors"])
