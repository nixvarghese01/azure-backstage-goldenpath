"""Service-to-service authentication and trusted user context.

Callers authenticate with a bearer token:

* ``entra`` mode (cloud): a Microsoft Entra access token from the caller's workload identity. The token
  audience must be this service's app ID, and the caller's object/app ID must be on the allowlist.
* ``static`` mode (local development only): a shared dev token from the environment.

User context (who the developer or approver is) is accepted **only** from an authenticated, allowlisted
caller - the Backstage bridge derives it from the verified Backstage user token. It is never taken from
the browser directly (see docs/architecture/microservices.md, trust rules).
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sportify_common.jwt_verify import TokenVerificationError, entra_verifier


@dataclass(frozen=True)
class UserContext:
    user_ref: str
    group_refs: tuple[str, ...] = field(default_factory=tuple)

    def in_group(self, group_ref: str) -> bool:
        return group_ref in self.group_refs


@dataclass(frozen=True)
class Caller:
    subject: str            # caller workload (Entra oid/appid, or "dev")
    user: UserContext | None


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    dev_token: str | None
    tenant_id: str | None
    audience: str | None
    allowed_callers: frozenset[str]

    @classmethod
    def from_env(cls) -> AuthSettings:
        mode = os.environ.get("SPORTIFY_AUTH_MODE", "entra").lower()
        if mode not in {"entra", "static"}:
            raise ValueError("SPORTIFY_AUTH_MODE must be 'entra' or 'static'")
        return cls(
            mode=mode,
            dev_token=os.environ.get("SPORTIFY_DEV_SERVICE_TOKEN"),
            tenant_id=os.environ.get("SPORTIFY_ENTRA_TENANT_ID"),
            audience=os.environ.get("SPORTIFY_ENTRA_AUDIENCE"),
            allowed_callers=frozenset(
                c.strip() for c in os.environ.get("SPORTIFY_ALLOWED_CALLERS", "").split(",") if c.strip()
            ),
        )


def _unauthorized(detail: str = "unauthorized") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def authenticate(settings: AuthSettings, authorization: str | None) -> str:
    """Return the caller subject or raise 401/403."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized()
    token = authorization.split(" ", 1)[1].strip()

    if settings.mode == "static":
        if not settings.dev_token or not hmac.compare_digest(token, settings.dev_token):
            raise _unauthorized()
        return "dev"

    if not settings.tenant_id or not settings.audience:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="auth not configured")
    try:
        claims = entra_verifier(settings.tenant_id, settings.audience).verify(token)
    except TokenVerificationError as exc:
        raise _unauthorized() from exc
    subject = str(claims.get("oid") or claims.get("azp") or claims.get("appid") or "")
    if not subject or subject not in settings.allowed_callers:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="caller not allowed")
    return subject


def _settings() -> AuthSettings:
    return AuthSettings.from_env()


def require_caller(
    authorization: Annotated[str | None, Header()] = None,
    x_sportify_user: Annotated[str | None, Header()] = None,
    x_sportify_groups: Annotated[str | None, Header()] = None,
    settings: AuthSettings = Depends(_settings),  # noqa: B008
) -> Caller:
    subject = authenticate(settings, authorization)
    user = None
    if x_sportify_user:
        groups = tuple(g.strip() for g in (x_sportify_groups or "").split(",") if g.strip())
        user = UserContext(user_ref=x_sportify_user.strip(), group_refs=groups)
    return Caller(subject=subject, user=user)


def require_user(caller: Annotated[Caller, Depends(require_caller)]) -> Caller:
    if caller.user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user context required")
    return caller
