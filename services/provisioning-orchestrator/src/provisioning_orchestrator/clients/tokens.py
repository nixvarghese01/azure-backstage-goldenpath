"""Bearer tokens for calling other platform services: Entra (cloud) or the static dev token (local)."""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _credential():  # type: ignore[no-untyped-def]
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def bearer_for(scope: str | None) -> str:
    if scope:
        access_token: str = _credential().get_token(scope).token
        return access_token
    token = os.environ.get("IDP_DEV_SERVICE_TOKEN")
    if not token:
        raise RuntimeError("no Entra scope configured and IDP_DEV_SERVICE_TOKEN is not set")
    return token
