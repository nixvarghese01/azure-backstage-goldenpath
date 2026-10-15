"""Password-file login for the dev in-cluster PostgreSQL (Key Vault secret mounted by the CSI driver)."""

from pathlib import Path

import pytest
from provisioning_orchestrator import db
from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.db import password_injector, read_password

FIRST, ROTATED = "first-value", "rotated-value"
MOUNTED = "/mnt/secrets/orchestrator-db-password"


def test_read_password_strips_the_trailing_newline(tmp_path: Path) -> None:
    secret = tmp_path / "orchestrator-db-password"
    secret.write_text(f"{FIRST}\n", encoding="utf-8")
    assert read_password(str(secret)) == FIRST


def test_password_file_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCHESTRATOR_DATABASE_PASSWORD_FILE", raising=False)
    assert Settings.from_env().database_password_file is None
    monkeypatch.setenv("ORCHESTRATOR_DATABASE_PASSWORD_FILE", MOUNTED)
    assert Settings.from_env().database_password_file == MOUNTED


def test_each_connection_reads_the_current_password(tmp_path: Path) -> None:
    secret = tmp_path / "pw"
    secret.write_text(f"{FIRST}\n", encoding="utf-8")
    inject = password_injector(str(secret))
    cparams: dict[str, str] = {}
    inject(None, None, [], cparams)
    assert cparams["password"] == FIRST
    secret.write_text(f"{ROTATED}\n", encoding="utf-8")  # rotation is picked up without a restart
    inject(None, None, [], cparams)
    assert cparams["password"] == ROTATED


def test_api_worker_and_migrations_share_one_engine_factory() -> None:
    """The migration Job failed with 'no password supplied' when it built its own engine."""
    root = Path(__file__).resolve().parents[1]
    for path in (
        "migrations/env.py",
        "src/provisioning_orchestrator/main.py",
        "src/provisioning_orchestrator/worker.py",
    ):
        source = (root / path).read_text(encoding="utf-8")
        assert "engine_from_settings(settings)" in source, path
        assert "make_engine(" not in source, path


def test_engine_from_settings_uses_the_password_file(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(db, "make_engine", lambda url, **kwargs: calls.append({"url": url, **kwargs}))
    monkeypatch.setenv(
        "ORCHESTRATOR_DATABASE_URL", "postgresql+psycopg://orchestrator@postgres:5432/orchestrator"
    )
    monkeypatch.setenv("ORCHESTRATOR_DATABASE_PASSWORD_FILE", MOUNTED)
    monkeypatch.setenv("ORCHESTRATOR_DATABASE_ENTRA_AUTH", "false")
    db.engine_from_settings(Settings.from_env())
    assert calls == [
        {
            "url": "postgresql+psycopg://orchestrator@postgres:5432/orchestrator",
            "entra_auth": False,
            "password_file": MOUNTED,
        }
    ]
