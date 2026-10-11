"""Initial schema: requests, steps, audit_events, inbox_events, outbox_messages.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

J = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("application_name", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("stack", sa.String(32), nullable=False),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        *[sa.Column(c, J, nullable=False) for c in (
            "spec", "validation", "repository", "platform", "plan", "approval", "protection_rule",
            "outputs", "application", "deployment", "cleanup", "runs", "error")],
        sa.Column("ready_for_repository", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_requests_idempotency_key"),
    )
    op.create_index("ix_requests_app_env", "requests", ["application_name", "environment"])
    op.create_index("ix_requests_state", "requests", ["state"])

    op.create_table(
        "steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.id"), nullable=True),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("dedup_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", J, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", TS, nullable=False),
        sa.Column("locked_until", TS, nullable=True),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_steps_dedup_key"),
    )
    op.create_index("ix_steps_claim", "steps", ["status", "run_after"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.id"), nullable=True),
        sa.Column("at", TS, nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", J, nullable=False),
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    # Append-only: the application role may insert and select audit rows, never update or delete them.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC")

    op.create_table(
        "inbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("delivery_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", J, nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.Column("processed_at", TS, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("delivery_id", name="uq_inbox_delivery_id"),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", J, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("next_attempt_at", TS, nullable=False),
        sa.Column("delivered_at", TS, nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    for table in ("outbox_messages", "inbox_events", "audit_events", "steps", "requests"):
        op.drop_table(table)
