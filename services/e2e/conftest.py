"""Cross-service end-to-end fixtures: real discovery app (mock Azure, real allowlist) wired into the real
orchestrator (mock GitHub), rendering the real NestJS stack template."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from azure_discovery.config import Settings as DiscoverySettings
from azure_discovery.inventory.mock import MockInventory
from azure_discovery.main import create_app as create_discovery
from azure_discovery.policy import load_allowlist
from provisioning_orchestrator.clients.backstage import NullBackstageClient
from provisioning_orchestrator.clients.github import MockGitHubClient
from provisioning_orchestrator.config import Settings as OrchestratorSettings
from provisioning_orchestrator.db import make_session_factory
from provisioning_orchestrator.engine import Context
from provisioning_orchestrator.main import create_app as create_orchestrator
from provisioning_orchestrator.models import Base
from provisioning_orchestrator.worker import Worker

REPO = Path(__file__).resolve().parents[2]
TOKEN = "e2e-token"  # noqa: S105 - test value
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class CapturingGitHub(MockGitHubClient):
    """Mock GitHub that also keeps the content of committed files."""

    def __init__(self) -> None:
        super().__init__()
        self.files: dict[str, dict[str, str]] = {}

    def commit_files_on_branch(self, repo: str, base: str, branch: str, files: dict[str, str],
                               message: str) -> str:
        self.files[branch] = dict(files)
        return super().commit_files_on_branch(repo, base, branch, files, message)


class InProcessDiscovery:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def validate(self, body: dict[str, Any]) -> dict[str, Any]:
        res = self.client.post("/v1/validate", json=body, headers=AUTH)
        res.raise_for_status()
        return res.json()  # type: ignore[no-any-return]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPORTIFY_AUTH_MODE", "static")
    monkeypatch.setenv("SPORTIFY_DEV_SERVICE_TOKEN", TOKEN)
    secret = tmp_path / "webhook"
    secret.write_text("e2e-webhook-secret")
    monkeypatch.setenv("ORCHESTRATOR_GITHUB_WEBHOOK_SECRET_FILE", str(secret))


@pytest.fixture
def inventory() -> MockInventory:
    return MockInventory()


@pytest.fixture
def discovery(inventory: MockInventory) -> TestClient:
    policy_file = REPO / "policies" / "allowlist.yaml"
    settings = DiscoverySettings(azure_mode="mock", policy_file=policy_file, cache_ttl_seconds=0, log_level="WARNING")
    return TestClient(create_discovery(settings, inventory, load_allowlist(policy_file)))


@pytest.fixture
def stacks(tmp_path: Path) -> Path:
    root = tmp_path / "stacks"
    applications = REPO / "templates" / "applications"
    shutil.copytree(applications / "_shared", root / "_shared")
    for stack in ("nestjs", "fastapi", "go", "dotnet", "springboot", "nextjs", "react", "vue"):
        shutil.copytree(applications / stack / "application", root / stack)
    return root


@pytest.fixture
def system(discovery: TestClient, stacks: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    settings = replace(OrchestratorSettings.from_env(), database_url="sqlite://", github_mode="mock",
                       stack_templates_dir=stacks, backstage_base_url="https://backstage.example",
                       reconcile_interval_seconds=3600)
    github = CapturingGitHub()
    ctx = Context(settings=settings, github=github, discovery=InProcessDiscovery(discovery),
                  backstage=NullBackstageClient(), sessions=sessions)
    return {
        "api": TestClient(create_orchestrator(settings, sessions)),
        "worker": Worker(ctx, worker_id="e2e"),
        "github": github,
        "backstage": ctx.backstage,
    }
