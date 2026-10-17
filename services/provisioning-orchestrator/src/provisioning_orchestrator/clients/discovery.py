"""Client for azure-discovery. The orchestrator re-validates every selection before acting on it."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from provisioning_orchestrator.clients.tokens import bearer_for


class DiscoveryClient(Protocol):
    def validate(self, body: dict[str, Any]) -> dict[str, Any]: ...


class HttpDiscoveryClient:
    def __init__(self, base_url: str, scope: str | None, timeout: float = 10.0) -> None:
        self.base_url = base_url
        self.scope = scope
        self.timeout = timeout

    def validate(self, body: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                res = httpx.post(
                    f"{self.base_url}/v1/validate",
                    json=body,
                    headers={"Authorization": f"Bearer {bearer_for(self.scope)}"},
                    timeout=self.timeout,
                )
                if res.status_code >= 500:
                    last_exc = RuntimeError(f"discovery returned {res.status_code}")
                    continue
                res.raise_for_status()
                return res.json()  # type: ignore[no-any-return]
            except httpx.TransportError as exc:
                last_exc = exc
        raise RuntimeError("discovery unavailable") from last_exc
