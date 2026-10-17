"""Backstage notifications client (orchestrator -> Backstage, through the outbox)."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from provisioning_orchestrator.clients.tokens import bearer_for


class BackstageClient(Protocol):
    def notify(
        self, recipients: list[str], title: str, description: str, link: str, severity: str
    ) -> None: ...

    def unregister_component(self, name: str, namespace: str = "default") -> None: ...


class HttpBackstageClient:
    def __init__(self, base_url: str, scope: str | None) -> None:
        self.base_url = base_url
        self.scope = scope

    def notify(self, recipients: list[str], title: str, description: str, link: str, severity: str) -> None:
        body: dict[str, Any] = {
            "recipients": {"type": "entity", "entityRef": recipients},
            "payload": {
                "title": title,
                "description": description,
                "link": link,
                "severity": severity,
                "topic": "idp-provisioning",
            },
        }
        res = httpx.post(
            f"{self.base_url}/api/notifications/notifications",
            json=body,
            headers={"Authorization": f"Bearer {bearer_for(self.scope)}"},
            timeout=5.0,
        )
        res.raise_for_status()

    def unregister_component(self, name: str, namespace: str = "default") -> None:
        """Remove a cleaned-up application from the catalog (idempotent: 404 is fine).

        First the location the scaffolder registered (catalog:register), else Backstage reads the entity
        back from it on the next refresh; then the entity itself.
        """
        headers = {"Authorization": f"Bearer {bearer_for(self.scope)}"}
        loc = httpx.get(
            f"{self.base_url}/api/catalog/locations/by-entity/component/{namespace}/{name}",
            headers=headers,
            timeout=5.0,
        )
        if loc.status_code == 200:
            res = httpx.delete(
                f"{self.base_url}/api/catalog/locations/{loc.json()['id']}", headers=headers, timeout=5.0
            )
            if res.status_code not in (204, 404):
                res.raise_for_status()
        elif loc.status_code != 404:
            loc.raise_for_status()
        res = httpx.get(
            f"{self.base_url}/api/catalog/entities/by-name/component/{namespace}/{name}",
            headers=headers,
            timeout=5.0,
        )
        if res.status_code == 404:
            return
        res.raise_for_status()
        uid = res.json()["metadata"]["uid"]
        res = httpx.delete(f"{self.base_url}/api/catalog/entities/by-uid/{uid}", headers=headers, timeout=5.0)
        if res.status_code not in (204, 404):
            res.raise_for_status()


class NullBackstageClient:
    """Used when Backstage notifications aren't configured (e.g. tests)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def notify(self, recipients: list[str], title: str, description: str, link: str, severity: str) -> None:
        self.sent.append(
            {
                "recipients": recipients,
                "title": title,
                "description": description,
                "link": link,
                "severity": severity,
            }
        )

    def unregister_component(self, name: str, namespace: str = "default") -> None:
        self.sent.append({"unregistered": f"component:{namespace}/{name}"})
