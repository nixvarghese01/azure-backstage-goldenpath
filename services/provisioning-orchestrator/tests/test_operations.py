"""Operations view (#115): current workload health, separate from the provisioning outcome."""

from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from provisioning_orchestrator.db import transaction
from provisioning_orchestrator.main import create_app
from provisioning_orchestrator.models import Request
from provisioning_orchestrator.operations import OperationsCache, WorkloadUnavailableError, assess_workload

from tests.conftest import APPROVER, REQUESTER, callback, drain

OTHER_TEAM = {**REQUESTER, "X-IDP-User": "user:default/eve", "X-IDP-Groups": "group:default/team-payments"}


def workload(ready: int = 2, desired: int = 2, image: str = "acr/orders-api:abc123", **pod: Any) -> dict:
    status = {"ready": True, **pod}
    return {
        "deployment": {
            "spec": {"replicas": desired, "template": {"spec": {"containers": [{"image": image}]}}},
            "status": {"readyReplicas": ready, "updatedReplicas": desired},
        },
        "pods": [
            {
                "metadata": {"name": f"orders-api-{i}"},
                "status": {
                    "phase": "Running",
                    "containerStatuses": [
                        {
                            "ready": i < ready and status["ready"],
                            "restartCount": status.get("restarts", 0),
                            "image": image,
                            "imageID": f"acr/orders-api@sha256:{'d' * 64}",
                            "state": {"waiting": {"reason": status["reason"]}} if "reason" in status else {},
                        }
                    ],
                },
            }
            for i in range(desired)
        ],
    }


class FakeReader:
    def __init__(self) -> None:
        self.result: Any = workload()
        self.calls = 0

    def read(self, namespace: str, name: str) -> dict | None:
        self.calls += 1
        assert (namespace, name) == ("orders-api", "orders-api")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def reader() -> FakeReader:
    return FakeReader()


@pytest.fixture
def ops_client(settings, sessions, reader) -> TestClient:
    return TestClient(create_app(replace(settings, operations_cache_seconds=0), sessions, reader))


def deployed_request(sessions, **changes: Any) -> str:
    fields: dict[str, Any] = {
        "idempotency_key": "ops-1",
        "application_name": "orders-api",
        "environment": "dev",
        "owner": "group:default/team-orders",
        "stack": "nestjs",
        "requested_by": "user:default/alex",
        "state": "SUCCEEDED",
        "spec": {"namespace": {"mode": "new", "name": "orders-api"}},
        "repository": {"name": "orders-api", "url": "https://github.com/nixvarghese01/orders-api.git"},
        "application": {"image": "acr/orders-api:abc123"},
        "deployment": {"endpoint": "orders-api.dev.xycorp.local", "revision": 2, "image_tag": "abc123"},
        "runs": [
            {
                "stage": "deploy",
                "status": "success",
                "url": "https://run/5",
                "at": "2026-10-20T10:00:00+00:00",
            }
        ],
        **changes,
    }
    with transaction(sessions) as s:
        req = Request(**fields)
        s.add(req)
        s.flush()
        return req.id


def ops(client: TestClient, rid: str, headers: dict = REQUESTER) -> dict:
    res = client.get(f"/v1/requests/{rid}/operations", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_healthy_workload_shows_version_and_last_deployment(ops_client, sessions) -> None:
    body = ops(ops_client, deployed_request(sessions))
    assert body["health"] == "healthy"
    assert body["provisioning_state"] == "SUCCEEDED"
    assert body["replicas"] == {"desired": 2, "ready": 2, "updated": 2}
    assert body["running"] == [{"image": "acr/orders-api:abc123", "digests": ["sha256:" + "d" * 64]}]
    assert body["matches_last_deployment"] is True
    assert body["last_deployment"] == {
        "at": "2026-10-20T10:00:00+00:00",
        "run_url": "https://run/5",
        "revision": 2,
        "image_tag": "abc123",
    }
    assert body["source"] == "kubernetes" and body["observed_at"] and body["stale"] is False


def test_failure_after_success_shows_degradation_not_new_history(ops_client, sessions, reader) -> None:
    rid = deployed_request(sessions)
    reader.result = workload(ready=1, desired=2, reason="CrashLoopBackOff", restarts=4)
    body = ops(ops_client, rid)
    assert body["health"] == "degraded"
    assert "CrashLoopBackOff" in body["summary"]
    assert body["provisioning_state"] == "SUCCEEDED"
    assert max(p["restarts"] for p in body["pods"]) == 4
    reader.result = workload(ready=0, desired=2, reason="CrashLoopBackOff")
    assert ops(ops_client, rid)["health"] == "down"


def test_deleted_workload_is_missing(ops_client, sessions, reader) -> None:
    reader.result = None
    assert ops(ops_client, deployed_request(sessions))["health"] == "missing"


def test_unreadable_cluster_is_unknown_never_healthy(ops_client, sessions, reader) -> None:
    rid = deployed_request(sessions)
    reader.result = WorkloadUnavailableError("unavailable", "Kubernetes API unreachable")
    body = ops(ops_client, rid)
    assert body["health"] == "unknown" and body["stale"] is True and body["observed_at"] is None
    assert body["unavailable"] == "unavailable"


def test_outage_keeps_the_last_observation_marked_stale(ops_client, sessions, reader) -> None:
    rid = deployed_request(sessions)
    assert ops(ops_client, rid)["health"] == "healthy"
    reader.result = WorkloadUnavailableError("permission_denied", "may not read")
    body = ops(ops_client, rid)
    assert body["health"] == "unknown"
    assert body["last_known_health"] == "healthy"
    assert body["stale"] is True and body["observed_at"]
    assert body["unavailable"] == "permission_denied"


def test_running_image_differs_from_the_last_deployment(ops_client, sessions, reader) -> None:
    reader.result = workload(image="acr/orders-api:hotfix")
    assert ops(ops_client, deployed_request(sessions))["matches_last_deployment"] is False


def test_other_teams_cannot_read_operations(ops_client, sessions) -> None:
    rid = deployed_request(sessions)
    res = ops_client.get(f"/v1/requests/{rid}/operations", headers=OTHER_TEAM)
    assert res.status_code == 403
    assert ops(ops_client, rid, APPROVER)["health"] == "healthy"  # approvers may look


def test_nothing_deployed_or_cleaned_up_skips_the_cluster(ops_client, sessions, reader) -> None:
    rid = deployed_request(sessions, state="APPLICATION_BUILDING", application={}, deployment={}, runs=[])
    assert ops(ops_client, rid)["health"] == "not_deployed"
    gone = deployed_request(sessions, idempotency_key="ops-2", state="CLEANED_UP")
    assert ops(ops_client, gone)["health"] == "removed"
    assert reader.calls == 0


def test_links_show_unconfigured_integrations(settings, sessions, reader) -> None:
    configured = replace(
        settings,
        operations_links={"dashboard": "https://grafana/d/app?var-ns={namespace}&var-env={environment}"},
    )
    client = TestClient(create_app(configured, sessions, reader))
    links = ops(client, deployed_request(sessions))["links"]
    assert links["dashboard"] == {
        "available": True,
        "url": "https://grafana/d/app?var-ns=orders-api&var-env=dev",
    }
    assert links["logs"] == {"available": False, "reason": "not configured"}
    assert links["repository"]["url"] == "https://github.com/nixvarghese01/orders-api"
    assert links["deployment"]["url"] == "https://run/5"
    assert links["runbook"]["url"].endswith("/docs/default/component/orders-api/#runbook")


def test_one_cluster_read_per_interval_whoever_asks() -> None:
    reader, now = FakeReader(), [0.0]
    cache = OperationsCache(reader, ttl=15, clock=lambda: now[0])
    for _ in range(5):
        cache.observe("r1", "orders-api", "orders-api")
    assert reader.calls == 1
    reader.result = WorkloadUnavailableError("unavailable", "down")
    now[0] = 16
    for _ in range(5):  # failures are cached too, so an outage isn't hammered
        cache.observe("r1", "orders-api", "orders-api")
    assert reader.calls == 2


def test_cache_is_bounded() -> None:
    reader = FakeReader()
    cache = OperationsCache(reader, ttl=60, max_entries=2)
    for key in ("a", "b", "c"):
        cache.observe(key, "orders-api", "orders-api")
    assert list(cache._entries) == ["b", "c"]


def test_scaled_to_zero_is_stopped_not_down() -> None:
    assert assess_workload(workload(ready=0, desired=0))["health"] == "stopped"


def test_a_later_deploy_updates_a_succeeded_request(client, worker, sessions) -> None:
    rid = deployed_request(sessions)
    callback(client, rid, "deploy", "success", 9, {"endpoint": "orders-api.dev.xycorp.local", "revision": 3})
    drain(worker)
    with transaction(sessions) as s:
        req = s.get(Request, rid)
        assert req is not None and req.state == "SUCCEEDED"
        assert req.deployment["revision"] == 3 and req.deployment["deployed_at"]
