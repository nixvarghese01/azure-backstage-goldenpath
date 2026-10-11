"""Database model. One database (``orchestrator``) owned exclusively by this service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JsonType, list[Any]: JsonType}


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_requests_idempotency_key"),
        Index("ix_requests_app_env", "application_name", "environment"),
        Index("ix_requests_state", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    application_name: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(200))
    stack: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(32))
    # Full form input (no secrets by construction) and derived data.
    spec: Mapped[dict[str, Any]] = mapped_column(default=dict)
    validation: Mapped[dict[str, Any]] = mapped_column(default=dict)
    ready_for_repository: Mapped[bool] = mapped_column(default=False)
    repository: Mapped[dict[str, Any]] = mapped_column(default=dict)      # {owner, name, url}
    platform: Mapped[dict[str, Any]] = mapped_column(default=dict)        # {pr_number, pr_url, apply_run}
    plan: Mapped[dict[str, Any]] = mapped_column(default=dict)            # {hash, run_id, summary}
    approval: Mapped[dict[str, Any]] = mapped_column(default=dict)        # {decision, by, at, comment, hash}
    protection_rule: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {callback_url, environment}
    outputs: Mapped[dict[str, Any]] = mapped_column(default=dict)         # non-sensitive TF outputs
    application: Mapped[dict[str, Any]] = mapped_column(default=dict)     # {pr_number, pr_url, image}
    deployment: Mapped[dict[str, Any]] = mapped_column(default=dict)      # {endpoint, pods, run_url}
    cleanup: Mapped[dict[str, Any]] = mapped_column(default=dict)         # {stage}
    runs: Mapped[list[Any]] = mapped_column(default=list)                 # workflow run history
    error: Mapped[dict[str, Any]] = mapped_column(default=dict)           # actionable diagnostics
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Step(Base):
    """Durable job queue entry. Claimed with SELECT ... FOR UPDATE SKIP LOCKED plus a lease."""

    __tablename__ = "steps"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_steps_dedup_key"),
        Index("ix_steps_claim", "status", "run_after"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(48))
    dedup_key: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|done|failed
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    """Append-only audit trail: who requested, who approved, what changed, which run produced it."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("requests.id"), nullable=True, index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)


class InboxEvent(Base):
    """Inbound GitHub webhooks and Actions callbacks, deduplicated by delivery ID."""

    __tablename__ = "inbox_events"
    __table_args__ = (UniqueConstraint("delivery_id", name="uq_inbox_delivery_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))          # github_webhook | actions_callback
    delivery_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutboxMessage(Base):
    """Notifications to Backstage, written in the same transaction as the state change."""

    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
