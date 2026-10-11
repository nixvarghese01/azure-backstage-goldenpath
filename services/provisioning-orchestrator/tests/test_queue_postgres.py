"""Concurrency guarantees that need real PostgreSQL (SKIP LOCKED). Run with: pytest -m integration"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select

from provisioning_orchestrator.db import make_session_factory, transaction
from provisioning_orchestrator.models import Base, Step
from provisioning_orchestrator.queue import claim_next

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
