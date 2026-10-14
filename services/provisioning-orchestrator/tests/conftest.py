from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from provisioning_orchestrator.clients.backstage import NullBackstageClient
from provisioning_orchestrator.clients.github import MockGitHubClient
from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.db import make_session_factory
from provisioning_orchestrator.engine import Context
from provisioning_orchestrator.main import create_app
from provisioning_orchestrator.models import Base
from provisioning_orchestrator.worker import Worker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

SUB = "00000000-0000-0000-0000-000000000000"
DEV = "dev-token"
REQUESTER = {
    "Authorization": f"Bearer {DEV}",
    "X-IDP-User": "user:default/alex",
    "X-IDP-Groups": "group:default/team-orders",
}
APPROVER = {
    "Authorization": f"Bearer {DEV}",
    "X-IDP-User": "user:default/sam",
    "X-IDP-Groups": "group:default/platform-approvers",
}
SERVICE = {"Authorization": f"Bearer {DEV}"}
WEBHOOK_SECRET = "test-webhook-secret"  # noqa: S105 - test value


class FakeDiscovery:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {
            "valid": True,
            "errors": [],
            "warnings": [],
            "platform_changes": [],
            "resolved": {"resource_group_id": f"/subscriptions/{SUB}/resourceGroups/rg"},
        }
        self.calls: list[dict[str, Any]] = []

    def validate(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(body)
        return self.result


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDP_AUTH_MODE", "static")
    monkeypatch.setenv("IDP_DEV_SERVICE_TOKEN", DEV)
    secret = tmp_path / "webhook-secret"
    secret.write_text(WEBHOOK_SECRET)
    monkeypatch.setenv("ORCHESTRATOR_GITHUB_WEBHOOK_SECRET_FILE", str(secret))


@pytest.fixture
def stack_dir(tmp_path: Path) -> Path:
    root = tmp_path / "stacks" / "nestjs"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.ts.j2").write_text("// [[ values.app ]] in [[ values.namespace ]]\n")
    (root / "Dockerfile").write_text("FROM node:24-alpine\n")
    return tmp_path / "stacks"


@pytest.fixture
def settings(stack_dir: Path) -> Settings:
    base = Settings.from_env()
    return replace(
        base,
        database_url="sqlite://",
        github_mode="mock",
        stack_templates_dir=stack_dir,
        backstage_base_url="http://backstage",
        reconcile_interval_seconds=3600,
    )


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


@pytest.fixture
def github() -> MockGitHubClient:
    return MockGitHubClient()


@pytest.fixture
def discovery() -> FakeDiscovery:
    return FakeDiscovery()


@pytest.fixture
def ctx(settings, sessions, github, discovery) -> Context:
    return Context(
        settings=settings,
        github=github,
        discovery=discovery,
        backstage=NullBackstageClient(),
        sessions=sessions,
    )


@pytest.fixture
def worker(ctx) -> Worker:
    return Worker(ctx, worker_id="test-worker")


@pytest.fixture
def client(settings, sessions) -> TestClient:
    return TestClient(create_app(settings, sessions))


@pytest.fixture
def client_factory(settings, sessions):
    """A client whose app runs with some settings changed, e.g. client_factory(approver_group=...)."""
    return lambda **changes: TestClient(create_app(replace(settings, **changes), sessions))


def submission(**overrides: Any) -> dict[str, Any]:
    body = {
        "idempotency_key": "scaffolder-task-0001",
        "application_name": "orders-api",
        "description": "Order management REST API",
        "owner": "group:default/team-orders",
        "environment": "dev",
        "region": "uksouth",
        "stack": "nestjs",
        "subscription": {"mode": "existing", "id": SUB},
        "resource_group": {"mode": "existing", "name": "rg-idp-apps-dev"},
        "aks_cluster": {"mode": "existing", "name": "aks-idp-shared-dev"},
        "container_registry": {"mode": "existing", "name": "acridpdev"},
        "namespace": {"mode": "new", "name": "orders-api"},
        "runtime_capability": {"type": "storage", "mode": "existing", "name": "stidpshareddev"},
        "availability": {"tier": "standard"},
        "endpoint_host": "orders-api.dev.xycorp.local",
    }
    body.update(overrides)
    return body


def drain(worker: Worker, rounds: int = 20) -> None:
    for _ in range(rounds):
        progressed = worker.process_inbox() > 0
        progressed = worker.run_one_step() or progressed
        worker.deliver_outbox()
        if not progressed:
            return


def callback(
    client: TestClient,
    request_id: str,
    stage: str,
    status: str,
    run_id: int,
    data: dict[str, Any] | None = None,
) -> None:
    res = client.post(
        "/v1/callbacks/actions",
        headers=SERVICE,
        json={
            "request_id": request_id,
            "stage": stage,
            "status": status,
            "run_id": run_id,
            "run_url": f"https://github.com/run/{run_id}",
            "data": data or {},
        },
    )
    assert res.status_code == 202, res.text


def webhook(client: TestClient, event: str, delivery: str, payload: dict[str, Any]):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
