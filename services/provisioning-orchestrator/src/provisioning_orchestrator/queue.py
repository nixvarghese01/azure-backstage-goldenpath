"""Durable job queue on PostgreSQL: claim with FOR UPDATE SKIP LOCKED and a lease.

A crashed worker's step becomes claimable again once its lease expires. Steps are idempotent through
their dedup keys and handler design, so re-running a step after a crash is safe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from provisioning_orchestrator.models import Step


def claim_next(session: Session, worker_id: str, lease_seconds: int) -> Step | None:
    now = datetime.now(UTC)
    stmt = (
        select(Step)
        .where(
            or_(
                and_(Step.status == "pending", Step.run_after <= now),
                and_(Step.status == "running", Step.locked_until < now),  # lease expired
            )
        )
        .order_by(Step.run_after, Step.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    step = session.scalar(stmt)
    if step is None:
        return None
    step.status = "running"
    step.attempts += 1
    step.locked_by = worker_id
    step.locked_until = now + timedelta(seconds=lease_seconds)
    return step


def complete(step: Step) -> None:
    step.status = "done"
    step.locked_until = None
    step.last_error = None


def retry_or_fail(step: Step, error: str, max_attempts: int) -> bool:
    """Schedule a retry with exponential backoff. Returns False when attempts are exhausted."""
    step.last_error = error[:2000]
    step.locked_until = None
    if step.attempts >= max_attempts:
        step.status = "failed"
        return False
    step.status = "pending"
    step.run_after = datetime.now(UTC) + timedelta(seconds=min(300, 5 * 2 ** (step.attempts - 1)))
    return True
