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
    res = client.post("/v1/requests", json=submission(idempotency_key="scaffolder-task-0002"), headers=REQUESTER)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "duplicate_application"


def test_repository_cannot_be_recorded_before_validation(client) -> None:
    rid = client.post("/v1/requests", json=submission(), headers=REQUESTER).json()["id"]
    res = client.post(f"/v1/requests/{rid}/repository", headers=SERVICE,
                      json={"owner": "sportify-org", "name": "orders-api", "url": "https://github.com/x"})
    assert res.status_code == 409


def test_webhook_rejects_bad_signature(client) -> None:
    res = client.post("/v1/webhooks/github", content=b"{}", headers={
        "X-GitHub-Event": "ping", "X-GitHub-Delivery": "d1", "X-Hub-Signature-256": "sha256=bad"})
    assert res.status_code == 401


def test_webhook_deduplicates_deliveries(client) -> None:
    assert webhook(client, "ping", "d-1", {"zen": "hi"}).json()["status"] == "accepted"
    assert webhook(client, "ping", "d-1", {"zen": "hi"}).json()["status"] == "duplicate"
