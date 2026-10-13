import pytest
from fastapi import HTTPException
from sportify_common.auth import AuthSettings, authenticate


def _static(token: str | None = "dev-token") -> AuthSettings:  # noqa: S107 - test fixture
    return AuthSettings(
        mode="static", dev_token=token, tenant_id=None, audience=None, allowed_callers=frozenset()
    )


def test_static_mode_accepts_matching_token() -> None:
    assert authenticate(_static(), "Bearer dev-token") == "dev"


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer wrong"])
def test_static_mode_rejects(header: str | None) -> None:
    with pytest.raises(HTTPException) as exc:
        authenticate(_static(), header)
    assert exc.value.status_code == 401


def test_static_mode_without_configured_token_rejects() -> None:
    with pytest.raises(HTTPException):
        authenticate(_static(token=None), "Bearer anything")
