"""Concurrency guarantees that need real PostgreSQL (SKIP LOCKED). Run with: pytest -m integration"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from provisioning_orchestrator.db import make_session_factory, transaction
from provisioning_orchestrator.main import create_app
from provisioning_orchestrator.models import Base, Request, Step
from provisioning_orchestrator.queue import claim_next
from sqlalchemy import create_engine, func, select

from tests.conftest import APPROVER

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_sessions():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg:
        engine = create_engine(pg.get_connection_url())
        Base.metadata.create_all(engine)
        yield make_session_factory(engine)


def test_each_step_is_claimed_exactly_once(pg_sessions) -> None:
    with transaction(pg_sessions) as s:
        for i in range(50):
            s.add(Step(kind="DISPATCH", dedup_key=f"k{i}", payload={}))

    def claim_all(worker: str) -> list[int]:
        got = []
        while True:
            with transaction(pg_sessions) as s:
                step = claim_next(s, worker, lease_seconds=60)
                if step is None:
                    return got
                got.append(step.id)

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(claim_all, [f"w{i}" for i in range(5)]))
    claimed = [i for r in results for i in r]
    assert len(claimed) == len(set(claimed)) == 50
    with transaction(pg_sessions) as s:
        assert s.scalar(select(func.count()).select_from(Step).where(Step.status == "running")) == 50


def test_concurrent_approvals_cannot_bypass_the_threshold(pg_sessions, settings) -> None:
    plan_hash = "c" * 64
    with transaction(pg_sessions) as s:
        req = Request(
            idempotency_key="concurrent-approvals",
            application_name="orders-api",
            environment="dev",
            owner="group:default/team-orders",
            stack="nestjs",
            requested_by="user:default/alex",
            state="AWAITING_APPROVAL",
            validation={"valid": True, "approvers_required": 2},
            plan={"hash": plan_hash, "run_id": "9"},
            protection_rule={"callback_url": "https://api.github.com/callback/9", "environment": "dev-infra"},
        )
        s.add(req)
        s.flush()
        rid = req.id
    app = create_app(settings, pg_sessions)

    def approve(user: str) -> int:
        with TestClient(app) as client:
            return client.post(
                f"/v1/requests/{rid}/approval",
                headers={**APPROVER, "X-IDP-User": f"user:default/{user}"},
                json={"decision": "approve", "plan_hash": plan_hash},
            ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:  # one approver submitting repeatedly counts once
        assert sorted(pool.map(approve, ["sam"] * 4)) == [200, 409, 409, 409]
    with ThreadPoolExecutor(max_workers=3) as pool:  # exactly one more distinct approval decides
        assert sorted(pool.map(approve, ["kim", "lee", "ana"])) == [200, 409, 409]
    with transaction(pg_sessions) as s:
        req = s.get(Request, rid)
        assert req is not None and req.state == "PROVISIONING"
        assert len(req.approval["approvals"]) == 2
        releases = select(func.count()).select_from(Step).where(Step.kind == "RELEASE_PROTECTION_RULE")
        assert s.scalar(releases.where(Step.request_id == rid)) == 1
