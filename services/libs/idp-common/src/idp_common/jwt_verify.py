"""JWT verification against a JWKS endpoint (Microsoft Entra ID, GitHub Actions OIDC)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient


class TokenVerificationError(Exception):
    """The token is missing, malformed, expired or not from a trusted issuer/audience."""


@dataclass(frozen=True)
class JwksVerifier:
    jwks_url: str
    issuer: str
    audience: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 60
    required_claims: tuple[str, ...] = field(default=("exp", "iat", "iss", "aud", "sub"))

    def verify(self, token: str) -> dict[str, Any]:
        try:
            signing_key = _jwks_client(self.jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={"require": list(self.required_claims)},
            )
        except jwt.PyJWTError as exc:
            raise TokenVerificationError(type(exc).__name__) from exc


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def entra_verifier(tenant_id: str, audience: str) -> JwksVerifier:
    return JwksVerifier(
        jwks_url=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        audience=audience,
    )


def github_actions_verifier(audience: str) -> JwksVerifier:
    return JwksVerifier(
        jwks_url="https://token.actions.githubusercontent.com/.well-known/jwks",
        issuer="https://token.actions.githubusercontent.com",
        audience=audience,
    )
