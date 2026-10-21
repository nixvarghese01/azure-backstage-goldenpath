"""Operational view of a deployed application: what runs now, observed in the cluster (#115).

Separate from the provisioning outcome: a request that succeeded yesterday says nothing about today.
Health comes from the workload (Deployment availability and pod readiness, whose probe is the
application's /health/ready), never from the last workflow status. When the cluster can't be read,
the view says unknown, keeping the last observation marked stale, and never healthy.

The orchestrator reads the cluster with its own ServiceAccount and a read-only role (deployments,
replicasets and pods; no Secrets, no logs). Browsers never get cluster or Azure credentials.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from provisioning_orchestrator.models import Request

_SA = Path("/var/run/secrets/kubernetes.io/serviceaccount")


class WorkloadUnavailableError(Exception):
    """The cluster couldn't be read; code is permission_denied | unavailable | not_configured."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class WorkloadReader(Protocol):
    def read(self, namespace: str, name: str) -> dict[str, Any] | None:
        """{deployment, pods} for the workload, or None when the Deployment doesn't exist."""


class NoClusterReader:
    """Outside a cluster (local development, tests): no operational data, said explicitly."""

    def read(self, namespace: str, name: str) -> dict[str, Any] | None:
        raise WorkloadUnavailableError("not_configured", "The orchestrator isn't running in a cluster.")


class KubernetesReader:
    """Reads the Kubernetes API with the pod's ServiceAccount token (no client library needed)."""

    def __init__(self, base_url: str, token_file: Path, ca_file: Path, timeout: float = 5.0) -> None:
        self.base_url = base_url
        self.token_file = token_file
        self.ca_file = ca_file
        self.timeout = timeout

    @classmethod
    def in_cluster(cls, host: str, port: str) -> KubernetesReader:
        return cls(f"https://{host}:{port}", _SA / "token", _SA / "ca.crt")

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any] | None:
        token = self.token_file.read_text(encoding="utf-8").strip()  # re-read: tokens are rotated
        try:
            res = httpx.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                verify=str(self.ca_file),
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise WorkloadUnavailableError("unavailable", f"Kubernetes API unreachable: {exc}") from None
        if res.status_code == 404:
            return None
        if res.status_code in (401, 403):
            raise WorkloadUnavailableError("permission_denied", "The orchestrator may not read the workload.")
        if res.status_code >= 400:
            raise WorkloadUnavailableError("unavailable", f"Kubernetes API answered {res.status_code}.")
        body: dict[str, Any] = res.json()
        return body

    def read(self, namespace: str, name: str) -> dict[str, Any] | None:
        deployment = self._get(f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}")
        if deployment is None:
            return None
        labels = (deployment.get("spec", {}).get("selector") or {}).get("matchLabels") or {}
        selector = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        pods = None
        if selector:
            pods = self._get(f"/api/v1/namespaces/{namespace}/pods", {"labelSelector": selector})
        return {"deployment": deployment, "pods": (pods or {}).get("items", [])}


def reader_from_env(env: dict[str, str]) -> WorkloadReader:
    host, port = env.get("KUBERNETES_SERVICE_HOST"), env.get("KUBERNETES_SERVICE_PORT", "443")
    if host and (_SA / "token").exists():
        return KubernetesReader.in_cluster(host, port)
    return NoClusterReader()


# ---------------------------------------------------------------------------------------------------
# Assessment: from raw objects to what an owner needs to know
# ---------------------------------------------------------------------------------------------------


def _pod(p: dict[str, Any]) -> dict[str, Any]:
    statuses = (p.get("status") or {}).get("containerStatuses") or []
    main = statuses[0] if statuses else {}
    waiting = (main.get("state") or {}).get("waiting") or {}
    terminated = (main.get("lastState") or {}).get("terminated") or {}
    return {
        "name": (p.get("metadata") or {}).get("name"),
        "phase": (p.get("status") or {}).get("phase"),
        "ready": bool(main.get("ready")),
        "restarts": sum(int(c.get("restartCount", 0)) for c in statuses),
        "reason": waiting.get("reason") or terminated.get("reason"),
        "image": main.get("image"),
        "digest": (main.get("imageID") or "").rpartition("@")[2] or None,
    }


def assess_workload(workload: dict[str, Any] | None) -> dict[str, Any]:
    """Health and running version from the observed Deployment and pods."""
    if workload is None:
        return {
            "health": "missing",
            "summary": "The deployment no longer exists in the cluster.",
            "replicas": None,
            "pods": [],
            "running": [],
        }
    dep = workload["deployment"]
    spec, status = dep.get("spec") or {}, dep.get("status") or {}
    desired = int(spec.get("replicas", 1))
    ready = int(status.get("readyReplicas", 0))
    updated = int(status.get("updatedReplicas", 0))
    pods = [_pod(p) for p in workload.get("pods", [])]
    conditions = {c.get("type"): c for c in status.get("conditions") or []}
    progressing = conditions.get("Progressing") or {}
    if desired == 0:
        health, summary = "stopped", "Scaled to zero replicas."
    elif ready == 0:
        health, summary = "down", "No replica is ready."
    elif ready < desired:
        health, summary = "degraded", f"{ready} of {desired} replicas are ready."
    elif progressing.get("reason") == "ProgressDeadlineExceeded":
        health, summary = "degraded", "The latest rollout is stuck."
    else:
        health, summary = "healthy", f"All {desired} replicas are ready."
    reasons = sorted({p["reason"] for p in pods if p["reason"] and not p["ready"]})
    if reasons and health != "healthy":
        summary += f" ({', '.join(reasons)})"
    containers = (spec.get("template") or {}).get("spec", {}).get("containers") or []
    image = containers[0].get("image") if containers else None
    digests = sorted({p["digest"] for p in pods if p["digest"]})
    return {
        "health": health,
        "summary": summary,
        "replicas": {"desired": desired, "ready": ready, "updated": updated},
        "pods": pods,
        "running": [{"image": image, "digests": digests}] if image else [],
    }


def last_deployment(req: Request) -> dict[str, Any] | None:
    """The newest successful deploy run, from the request's own history."""
    for run in reversed(req.runs or []):
        if run.get("stage") == "deploy" and run.get("status") == "success":
            return {
                "at": run.get("at"),
                "run_url": run.get("url"),
                "revision": req.deployment.get("revision"),
                "image_tag": req.deployment.get("image_tag"),
            }
    return None


def _link(template: str | None, values: dict[str, str]) -> dict[str, Any]:
    if not template:
        return {"available": False, "reason": "not configured"}
    return {"available": True, "url": template.format(**values)}


def links(req: Request, templates: dict[str, str | None], urls: dict[str, str]) -> dict[str, Any]:
    values = {
        "app": req.application_name,
        "namespace": req.spec.get("namespace", {}).get("name", req.application_name),
        "environment": req.environment,
        "request_id": req.id,
    }
    repo = urls.get("repository")
    deploy = last_deployment(req)
    out: dict[str, Any] = {
        "application": {"available": "application" in urls, "url": urls.get("application")},
        "repository": {"available": bool(repo), "url": repo},
        "deployment": {
            "available": bool(deploy and deploy.get("run_url")),
            "url": (deploy or {}).get("run_url"),
        },
        # The generated repository's TechDocs carry the runbook section.
        "runbook": {
            "available": "backstage" in urls,
            "url": urls.get("backstage", "").replace("/catalog/", "/docs/") + "/#runbook",
        },
    }
    for kind in ("dashboard", "logs", "traces"):  # filled in by the monitoring stack (#107)
        out[kind] = _link(templates.get(kind), values)
    return {
        k: v if v.get("available") else {"available": False, "reason": v.get("reason", "not available")}
        for k, v in out.items()
    }


# ---------------------------------------------------------------------------------------------------
# Bounded polling: one cluster read per request per interval, whoever asks
# ---------------------------------------------------------------------------------------------------


@dataclass
class _Entry:
    fetched: float
    observed_at: str
    data: dict[str, Any] | None = None
    error: WorkloadUnavailableError | None = None


@dataclass
class OperationsCache:
    """Caches each workload's observation for ttl seconds (errors too), and keeps the last good one so
    an outage shows it as stale instead of hiding it or calling it healthy."""

    reader: WorkloadReader
    ttl: float = 15.0
    max_entries: int = 500
    clock: Any = time.monotonic
    _entries: OrderedDict[str, _Entry] = field(default_factory=OrderedDict)
    _good: dict[str, _Entry] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, key: str, namespace: str, name: str) -> dict[str, Any]:
        now = self.clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or now - entry.fetched >= self.ttl:
                entry = self._fetch(namespace, name, now)
                self._entries[key] = entry
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    old, _ = self._entries.popitem(last=False)
                    self._good.pop(old, None)
                if entry.error is None:
                    self._good[key] = entry
            good = self._good.get(key)
        if entry.error is None:
            return {
                "source": "kubernetes",
                "observed_at": entry.observed_at,
                "stale": False,
                **assess_workload(entry.data),
            }
        result: dict[str, Any] = {
            "source": "kubernetes",
            "health": "unknown",
            "summary": str(entry.error),
            "unavailable": entry.error.code,
            "stale": True,
            "observed_at": None,
            "replicas": None,
            "pods": [],
            "running": [],
        }
        if good is not None:  # the last observation, clearly marked as old
            last = assess_workload(good.data)
            result.update({k: last[k] for k in ("replicas", "pods", "running")})
            result["observed_at"] = good.observed_at
            result["last_known_health"] = last["health"]
            result["age_seconds"] = round(now - good.fetched)
        return result

    def _fetch(self, namespace: str, name: str, now: float) -> _Entry:
        at = datetime.now(UTC).isoformat()
        try:
            return _Entry(fetched=now, observed_at=at, data=self.reader.read(namespace, name))
        except WorkloadUnavailableError as exc:
            return _Entry(fetched=now, observed_at=at, error=exc)
