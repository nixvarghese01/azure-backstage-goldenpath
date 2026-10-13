from types import SimpleNamespace

import pytest

from tests.conftest import REQUESTER, SERVICE, submission, webhook


def test_submit_requires_user_context(client) -> None:
    assert client.post("/v1/requests", json=submission(), headers=SERVICE).status_code == 400


def test_submit_requires_owner_membership(client) -> None:
    headers = {**REQUESTER, "X-Sportify-Groups": "group:default/other-team"}
    res = client.post("/v1/requests", json=submission(), headers=headers)
    assert res.status_code == 403


def test_duplicate_submission_returns_same_request(client) -> None:
    a = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()
    b = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()
    assert a["id"] == b["id"]
    assert a["state"] == "REQUESTED"


def test_second_active_request_for_same_app_conflicts(client) -> None:
    client.post("/v1/requests", json=submission(), headers=REQUESTER)
    res = client.post(
        "/v1/requests", json=submission(idempotency_key="scaffolder-task-0002"), headers=REQUESTER
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "duplicate_application"


def test_repository_cannot_be_recorded_before_validation(client) -> None:
    rid = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    res = client.post(
        f"/v1/requests/{rid}/repository",
        headers=SERVICE,
        json={"owner": "sportify-org", "name": "orders-api", "url": "https://github.com/x"},
    )
    assert res.status_code == 409


def test_webhook_rejects_bad_signature(client) -> None:
    res = client.post(
        "/v1/webhooks/github",
        content=b"{}",
        headers={"X-GitHub-Event": "ping", "X-GitHub-Delivery": "d1", "X-Hub-Signature-256": "sha256=bad"},
    )
    assert res.status_code == 401


def test_webhook_deduplicates_deliveries(client) -> None:
    assert webhook(client, "ping", "d-1", {"zen": "hi"}).json()["status"] == "accepted"
    assert webhook(client, "ping", "d-1", {"zen": "hi"}).json()["status"] == "duplicate"


@pytest.mark.parametrize("run_id, expected_status", [(42, 202), (43, 403), (None, 403)])
def test_actions_callback_binds_run_id_to_token(client, monkeypatch, run_id, expected_status) -> None:
    rid = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    monkeypatch.setenv("SPORTIFY_AUTH_MODE", "entra")
    claims = {
        "repository": "sportify-org/azure-backstage-goldenpath",
        "repository_owner": "sportify-org",
        "run_id": "42",
        "run_attempt": "1",
    }
    monkeypatch.setattr(
        "provisioning_orchestrator.main.github_actions_verifier",
        lambda _: SimpleNamespace(verify=lambda token: claims),
    )
    res = client.post(
        "/v1/callbacks/actions",
        headers=SERVICE,
        json={"request_id": rid, "stage": "platform_apply", "status": "success", "run_id": run_id},
    )
    assert res.status_code == expected_status, res.text
    if expected_status == 403:
        assert res.json()["detail"]["code"] == "wrong_run"


def test_callback_deduplication_is_scoped_to_request(client) -> None:
    first = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    second = client.post(
        "/v1/requests",
        json=submission(application_name="payments-api", idempotency_key="scaffolder-task-0002"),
        headers=REQUESTER,
    ).json()["id"]
    for rid in (first, second):
        body = {"request_id": rid, "stage": "platform_apply", "status": "success", "run_id": 42}
        assert client.post("/v1/callbacks/actions", headers=SERVICE, json=body).json()["status"] == "accepted"
        assert (
            client.post("/v1/callbacks/actions", headers=SERVICE, json=body).json()["status"] == "duplicate"
        )
