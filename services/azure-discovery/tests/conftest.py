from pathlib import Path

import pytest
from azure_discovery.config import Settings
from azure_discovery.inventory.mock import MockInventory
from azure_discovery.main import create_app
from azure_discovery.policy import load_allowlist
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_FILE = REPO_ROOT / "policies" / "allowlist.yaml"
SUB = "00000000-0000-0000-0000-000000000000"
AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def _static_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTIFY_AUTH_MODE", "static")
    monkeypatch.setenv("SPORTIFY_DEV_SERVICE_TOKEN", "test-token")


@pytest.fixture
def policy():
    return load_allowlist(POLICY_FILE)


@pytest.fixture
def inventory() -> MockInventory:
    return MockInventory()


@pytest.fixture
def client(inventory, policy) -> TestClient:
    settings = Settings(azure_mode="mock", policy_file=POLICY_FILE, cache_ttl_seconds=0, log_level="WARNING")
    return TestClient(create_app(settings, inventory, policy))


def base_request(**overrides) -> dict:
    req = {
        "application_name": "orders-api",
        "environment": "dev",
        "region": "uksouth",
        "subscription": {"mode": "existing", "id": SUB},
        "resource_group": {"mode": "existing", "name": "rg-sportify-apps-dev"},
        "aks_cluster": {"mode": "existing", "name": "aks-sportify-shared-dev"},
        "container_registry": {"mode": "existing", "name": "acrsportifydev"},
        "namespace": {"mode": "new", "name": "orders-api"},
        "runtime_capability": {"type": "storage", "mode": "existing", "name": "stsportifyshareddev"},
        "availability": {"tier": "standard"},
        "stack": "nestjs",
    }
    req.update(overrides)
    return req
