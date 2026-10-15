"""Password-file login for the dev in-cluster PostgreSQL (Key Vault secret mounted by the CSI driver)."""

from pathlib import Path

import pytest
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
