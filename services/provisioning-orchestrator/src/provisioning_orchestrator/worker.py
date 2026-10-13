"""Worker process: runs queued steps, processes the inbox, delivers the outbox and reconciles."""

from __future__ import annotations

import logging
import os
import signal
import socket
import time
from datetime import UTC, datetime, timedelta

from sportify_common.logging import configure_logging, request_id_var
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from provisioning_orchestrator.clients.backstage import HttpBackstageClient, NullBackstageClient
from provisioning_orchestrator.clients.discovery import HttpDiscoveryClient
from provisioning_orchestrator.clients.github import AppGitHubClient, GitHubClient, MockGitHubClient
from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.db import make_engine, make_session_factory, transaction
from provisioning_orchestrator.engine import (
    UUID_RE,
    Context,
    RetryLaterError,
    deliver_outbox_message,
    process_inbox_event,
    run_step,
)
from provisioning_orchestrator.models import InboxEvent, OutboxMessage, Request, Step
from provisioning_orchestrator.queue import claim_next, complete, retry_or_fail
from provisioning_orchestrator.service import fail
from provisioning_orchestrator.states import State

log = logging.getLogger("worker")

# Workflows that report progress for a request in each waiting state (for reconciliation).
_WATCH = {
    State.REPOSITORY_CREATED: ["terraform-validate.yml", "terraform-plan.yml"],
    State.PROVISIONING: ["terraform-apply.yml"],
    State.APPLICATION_BUILDING: ["application-ci.yml", "application-deploy.yml"],
    State.DEPLOYING: ["application-deploy.yml"],
}
_STALE_AFTER = timedelta(hours=6)


class Worker:
    def __init__(self, ctx: Context, worker_id: str | None = None) -> None:
        self.ctx = ctx
        self.sessions: sessionmaker[Session] = ctx.sessions
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
        self._stop = False
        self._last_reconcile = 0.0

    def stop(self, *_: object) -> None:
        log.info("stopping after the current iteration")
        self._stop = True

    # ------------------------------------------------------------------ steps
    def run_one_step(self) -> bool:
        s = self.ctx.settings
        with transaction(self.sessions) as session:
            step = claim_next(session, self.worker_id, s.worker_lease_seconds)
            step_id = step.id if step else None
        if step_id is None:
            return False
        try:
            with transaction(self.sessions) as session:
                step = session.get(Step, step_id)
                assert step is not None
                request_id_var.set(step.request_id)
                run_step(self.ctx, session, step)
                complete(step)
        except RetryLaterError as exc:
            with transaction(self.sessions) as session:
                step = session.get(Step, step_id)
                assert step is not None
                step.attempts = max(0, step.attempts - 1)  # waiting isn't a failure
                retry_or_fail(step, str(exc), max_attempts=10_000)
        except Exception as exc:
            log.exception("step %s failed", step_id)
            with transaction(self.sessions) as session:
                step = session.get(Step, step_id)
                assert step is not None
                if not retry_or_fail(step, f"{type(exc).__name__}: {exc}", s.max_step_attempts):
                    req = session.get(Request, step.request_id) if step.request_id else None
                    if req and req.state not in {
                        State.FAILED,
                        State.CANCELLED,
                        State.CLEANED_UP,
                        State.CLEANUP_PENDING,
                        State.SUCCEEDED,
                    }:
                        fail(
                            session,
                            req,
                            actor="orchestrator",
                            stage=step.kind.lower(),
                            message=(
                                f"{step.kind} failed after {step.attempts} attempts: {type(exc).__name__}"
                            ),
                        )
        finally:
            request_id_var.set(None)
        return True

    # ------------------------------------------------------------------ inbox
    def process_inbox(self, batch: int = 20) -> int:
        with transaction(self.sessions) as session:
            ids = list(
                session.scalars(
                    select(InboxEvent.id)
                    .where(InboxEvent.processed_at.is_(None))
                    .order_by(InboxEvent.id)
                    .limit(batch)
                    .with_for_update(skip_locked=True)
                )
            )
        for event_id in ids:
            try:
                with transaction(self.sessions) as session:
                    ev = session.get(InboxEvent, event_id)
                    if ev is None or ev.processed_at is not None:
                        continue
                    process_inbox_event(self.ctx, session, ev)
            except Exception as exc:
                log.exception("inbox event %s failed", event_id)
                with transaction(self.sessions) as session:
                    ev = session.get(InboxEvent, event_id)
                    if ev:
                        ev.error = f"{type(exc).__name__}: {exc}"[:2000]
                        ev.processed_at = datetime.now(UTC)
        return len(ids)

    # ------------------------------------------------------------------ outbox
    def deliver_outbox(self, batch: int = 20) -> int:
        now = datetime.now(UTC)
        with transaction(self.sessions) as session:
            msgs = list(
                session.scalars(
                    select(OutboxMessage)
                    .where(OutboxMessage.delivered_at.is_(None), OutboxMessage.next_attempt_at <= now)
                    .order_by(OutboxMessage.id)
                    .limit(batch)
                    .with_for_update(skip_locked=True)
                )
            )
            for msg in msgs:
                try:
                    deliver_outbox_message(self.ctx, msg)
                    msg.delivered_at = datetime.now(UTC)
                except Exception as exc:
                    msg.attempts += 1
                    msg.last_error = f"{type(exc).__name__}"[:500]
                    msg.next_attempt_at = now + timedelta(seconds=min(3600, 10 * 2**msg.attempts))
        return len(msgs)

    # ------------------------------------------------------------------ reconcile
    def reconcile(self) -> None:
        """Catch lost webhooks/callbacks: a failed run for a waiting request fails the request."""
        with transaction(self.sessions) as session:
            waiting = list(
                session.scalars(select(Request).where(Request.state.in_([st.value for st in _WATCH])))
            )
            for req in waiting:
                repo = req.repository.get("name")
                if not repo:
                    continue
                for wf in _WATCH[State(req.state)]:
                    try:
                        runs = self.ctx.github.list_runs(repo, wf, per_page=20)
                    except Exception:
                        log.warning("cannot list %s runs for %s", wf, repo, exc_info=True)
                        continue
                    for run in runs:
                        m = UUID_RE.search(run.display_title or "")
                        if (
                            m
                            and m.group(0) == req.id
                            and run.status == "completed"
                            and run.conclusion not in (None, "success", "skipped")
                        ):
                            fail(
                                session,
                                req,
                                actor="orchestrator",
                                stage=wf,
                                message=f"Workflow {wf} concluded '{run.conclusion}'.",
                                details={"run_url": run.html_url},
                            )
                            break
                    if req.state == State.FAILED:
                        break
                if (
                    req.state not in {State.FAILED}
                    and datetime.now(UTC) - req.updated_at.replace(tzinfo=req.updated_at.tzinfo or UTC)
                    > _STALE_AFTER
                ):
                    fail(
                        session,
                        req,
                        actor="orchestrator",
                        stage=req.state.lower(),
                        message="No progress for 6 hours; check the workflow runs and retry.",
                    )

    # ------------------------------------------------------------------ loop
    def run_forever(self) -> None:
        s = self.ctx.settings
        while not self._stop:
            did = self.process_inbox() > 0
            did = self.run_one_step() or did
            did = self.deliver_outbox() > 0 or did
            if time.monotonic() - self._last_reconcile >= s.reconcile_interval_seconds:
                self.reconcile()
                self._last_reconcile = time.monotonic()
            if not did:
                time.sleep(s.worker_poll_seconds)


def build_context(settings: Settings) -> Context:
    sessions = make_session_factory(
        make_engine(settings.database_url, entra_auth=settings.database_entra_auth)
    )
    github: GitHubClient
    if settings.github_mode == "mock":
        github = MockGitHubClient()
    else:
        if not (settings.github_app_id and settings.github_installation_id):
            raise RuntimeError("GitHub App ID and installation ID are required in 'app' mode")
        github = AppGitHubClient(settings.github_org, settings.github_app_id, settings.github_installation_id)
    backstage = (
        HttpBackstageClient(settings.backstage_base_url, settings.backstage_scope)
        if settings.backstage_base_url
        else NullBackstageClient()
    )
    return Context(
        settings=settings,
        github=github,
        discovery=HttpDiscoveryClient(settings.discovery_base_url, settings.discovery_scope),
        backstage=backstage,
        sessions=sessions,
    )


def main() -> None:  # pragma: no cover
    settings = Settings.from_env()
    configure_logging("provisioning-orchestrator-worker", settings.log_level)
    worker = Worker(build_context(settings))
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
