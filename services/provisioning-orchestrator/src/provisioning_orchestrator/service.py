"""Domain operations. Every state change goes through ``transition`` so it is validated, audited and
notified (outbox) inside the caller's transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from provisioning_orchestrator.models import AuditEvent, OutboxMessage, Request, Step
from provisioning_orchestrator.states import State, check_transition

# States that produce a Backstage notification, and to whom.
_NOTIFY: dict[State, tuple[str, str]] = {
    State.AWAITING_APPROVAL: ("approvers", "Approval needed"),
    State.SUCCEEDED: ("owner", "Deployed"),
    State.FAILED: ("owner", "Request failed"),
    State.CANCELLED: ("owner", "Request cancelled"),
    State.CLEANED_UP: ("owner", "Cleanup finished"),
}


def audit(session: Session, request_id: str | None, actor: str, action: str, **details: Any) -> None:
    session.add(AuditEvent(request_id=request_id, actor=actor, action=action, details=details))


def transition(
    session: Session, req: Request, target: State, *, actor: str, reason: str | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    current = State(req.state)
    if current == target:
        return  # idempotent: replayed events don't move or re-notify
    check_transition(current, target)
    req.state = target.value
    if error is not None:
        req.error = error
    audit(session, req.id, actor, "state_changed", **{"from": current.value, "to": target.value,
                                                      "reason": reason})
    if target in _NOTIFY:
        audience, title = _NOTIFY[target]
        session.add(OutboxMessage(kind="notification", payload={
            "request_id": req.id,
            "application": req.application_name,
            "audience": audience,
            "owner": req.owner,
            "requested_by": req.requested_by,
            "title": f"{title}: {req.application_name} ({req.environment})",
            "state": target.value,
            "error": (error or {}).get("message"),
        }))


def enqueue(
    session: Session, kind: str, *, request_id: str | None, dedup_key: str,
    payload: dict[str, Any] | None = None, delay_seconds: int = 0,
) -> bool:
    """Add a step unless one with the same dedup key exists. Returns True if added."""
    if session.scalar(select(Step.id).where(Step.dedup_key == dedup_key)) is not None:
        return False
    try:
        with session.begin_nested():
            session.add(Step(
                request_id=request_id, kind=kind, dedup_key=dedup_key, payload=payload or {},
                run_after=datetime.now(UTC) + timedelta(seconds=delay_seconds),
            ))
        return True
    except IntegrityError:  # concurrent enqueue of the same step
        return False


def record_run(req: Request, *, stage: str, run_id: str | int | None, url: str | None, status: str) -> None:
    runs = list(req.runs or [])
    runs.append({"stage": stage, "run_id": str(run_id) if run_id else None, "url": url, "status": status,
                 "at": datetime.now(UTC).isoformat()})
    req.runs = runs[-50:]


def fail(session: Session, req: Request, *, actor: str, stage: str, message: str,
         details: dict[str, Any] | None = None) -> None:
    error = {"stage": stage, "message": message, **(details or {})}
    transition(session, req, State.FAILED, actor=actor, reason=message, error=error)
