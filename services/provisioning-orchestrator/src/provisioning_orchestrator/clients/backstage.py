"""Backstage notifications client (orchestrator -> Backstage, through the outbox)."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from provisioning_orchestrator.clients.tokens import bearer_for


class BackstageClient(Protocol):
    def notify(self, recipients: list[str], title: str, description: str, link: str, severity: str) -> None: ...


class HttpBackstageClient:
    def __init__(self, base_url: str, scope: str | None) -> None:
        self.base_url = base_url
        self.scope = scope

    def notify(self, recipients: list[str], title: str, description: str, link: str, severity: str) -> None:
        body: dict[str, Any] = {
            "recipients": {"type": "entity", "entityRef": recipients},
            "payload": {"title": title, "description": description, "link": link,
                        "severity": severity, "topic": "sportify-provisioning"},
        }
        res = httpx.post(
            f"{self.base_url}/api/notifications/notifications",
            json=body,
            headers={"Authorization": f"Bearer {bearer_for(self.scope)}"},
            timeout=5.0,
        )
        res.raise_for_status()


class NullBackstageClient:
    """Used when Backstage notifications aren't configured (e.g. tests)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def notify(self, recipients: list[str], title: str, description: str, link: str, severity: str) -> None:
        self.sent.append({"recipients": recipients, "title": title, "description": description,
                          "link": link, "severity": severity})
