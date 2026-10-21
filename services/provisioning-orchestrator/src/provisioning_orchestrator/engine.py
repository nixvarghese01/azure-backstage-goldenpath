"""Step handlers and inbound event processing.

The worker runs each step in its own transaction. Handlers are idempotent: dispatches are deduplicated
by step keys, branches are force-moved on retry, PRs are reused if already open, and replayed events
can't move a request backwards or apply a plan twice.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from provisioning_orchestrator.clients.backstage import BackstageClient
from provisioning_orchestrator.clients.discovery import DiscoveryClient
from provisioning_orchestrator.clients.github import OIDC_SUBJECT_CLAIMS, GitHubClient
from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.models import AuditEvent, InboxEvent, OutboxMessage, Request, Step
from provisioning_orchestrator.service import audit, enqueue, fail, record_run, transition
from provisioning_orchestrator.states import ACTIVE, State
from provisioning_orchestrator.templating import render_stack

log = logging.getLogger(__name__)
ACTOR = "orchestrator"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RUN_ID_RE = re.compile(r"/actions/runs/(\d+)")


class RetryLaterError(Exception):
    """Step can't complete yet (e.g. PR checks still running); retry with backoff."""


class RetryNotPossibleError(Exception):
    """A failed request can't be resumed automatically (clean up and request again)."""


@dataclass
class Context:
    settings: Settings
    github: GitHubClient
    discovery: DiscoveryClient
    backstage: BackstageClient
    sessions: sessionmaker[Session]


# =====================================================================================================
# Helpers
# =====================================================================================================


def _app_repo(req: Request) -> str:
    return str(req.repository.get("name") or req.application_name)


def _validation_body(req: Request) -> dict[str, Any]:
    s = req.spec
    return {
        "application_name": req.application_name,
        "environment": req.environment,
        "region": s["region"],
        "tenant_id": s.get("tenant_id"),
        "management_group": s.get("management_group"),
        "subscription": s["subscription"],
        "resource_group": s["resource_group"],
        "aks_cluster": s["aks_cluster"],
        "container_registry": s["container_registry"],
        "namespace": s["namespace"],
        "runtime_capability": s.get("runtime_capability", {"type": "none", "mode": "existing"}),
        "availability": s.get("availability", {"tier": "standard"}),
        "stack": req.stack,
        "endpoint_host": s.get("endpoint_host", ""),
    }


def _dispatch(
    session: Session,
    req: Request,
    workflow: str,
    inputs: dict[str, str],
    *,
    key: str,
    repo: str | None = None,
) -> None:
    enqueue(
        session,
        "DISPATCH",
        request_id=req.id,
        dedup_key=key,
        payload={
            "repo": repo or _app_repo(req),
            "workflow": workflow,
            "inputs": {"request_id": req.id, **inputs},
        },
    )


def cleanup_step_failed(s: Session, req: Request, stage: str, run_url: str | None) -> None:
    """A cleanup workflow failed: record it (Clean up retries from here) instead of failing the request."""
    if (req.cleanup or {}).get("stage") == f"{stage}_failed":
        return
    req.cleanup = {**req.cleanup, "stage": f"{stage}_failed", "run_url": run_url}
    audit(s, req.id, ACTOR, "cleanup_step_failed", stage=stage, run=run_url)


# =====================================================================================================
# Step handlers
# =====================================================================================================


def h_validate(ctx: Context, s: Session, step: Step, req: Request) -> None:
    if req.state == State.REQUESTED:
        transition(s, req, State.VALIDATING, actor=ACTOR)
    result = ctx.discovery.validate(_validation_body(req))
    req.validation = result
    audit(
        s,
        req.id,
        ACTOR,
        "validated",
        valid=result.get("valid"),
        errors=result.get("errors", []),
        warnings=result.get("warnings", []),
    )
    if not result.get("valid"):
        msgs = "; ".join(f"{e['field']}: {e['message']}" for e in result.get("errors", []))
        fail(
            s,
            req,
            actor=ACTOR,
            stage="validate",
            message=f"Validation failed. {msgs}",
            details={"errors": result.get("errors", [])},
        )
        return
    # Persist the derived default (<app>.<gateway domain>) when the form left the host empty.
    host = result.get("resolved", {}).get("endpoint_host")
    if host and not req.spec.get("endpoint_host"):
        req.spec = {**req.spec, "endpoint_host": host}
    changes = result.get("platform_changes") or []
    if changes:
        req.platform = {**req.platform, "changes": changes}
        transition(s, req, State.PLATFORM_PROVISIONING, actor=ACTOR, reason=", ".join(changes))
        enqueue(s, "PLATFORM_REQUEST", request_id=req.id, dedup_key=f"platform-request:{req.id}")
    else:
        req.ready_for_repository = True


def _platform_files(req: Request) -> tuple[dict[str, str], list[str]]:
    spec, env = req.spec, req.environment
    files: dict[str, str] = {}
    stacks: list[str] = []
    meta = {"request_id": req.id, "requested_by": req.requested_by, "owner": req.owner}
    if spec["subscription"]["mode"] == "new":
        name = spec["subscription"]["name"]
        files[f"iac/platform/05-subscriptions/subscriptions.d/{name}.json"] = (
            json.dumps({"name": name, "environment": env, **meta}, indent=2) + "\n"
        )
        stacks.append("05-subscriptions")
    if spec["aks_cluster"]["mode"] == "new":
        name = spec["aks_cluster"]["name"]
        files[f"iac/platform/20-shared-{env}/clusters.d/{name}.json"] = (
            json.dumps(
                {
                    "name": name,
                    "location": spec["region"],
                    "zonal": spec.get("availability", {}).get("tier") == "ha",
                    **meta,
                },
                indent=2,
            )
            + "\n"
        )
    if spec["container_registry"]["mode"] == "new":
        name = spec["container_registry"]["name"]
        files[f"iac/platform/20-shared-{env}/registries.d/{name}.json"] = (
            json.dumps({"name": name, "location": spec["region"], **meta}, indent=2) + "\n"
        )
    if any(p.startswith(f"iac/platform/20-shared-{env}/") for p in files):
        stacks.append(f"20-shared-{env}")
    return files, stacks


def h_platform_request(ctx: Context, s: Session, step: Step, req: Request) -> None:
    if req.platform.get("pr_number"):
        return
    files, stacks = _platform_files(req)
    branch = f"idp/platform-{req.id}"
    repo = ctx.settings.platform_repo
    ctx.github.commit_files_on_branch(
        repo,
        ctx.settings.platform_repo_ref,
        branch,
        files,
        f"platform: resources for {req.application_name} ({req.id})",
    )
    pr = ctx.github.open_pull_request(
        repo,
        branch,
        ctx.settings.platform_repo_ref,
        f"Platform request: {', '.join(req.platform.get('changes', []))} for {req.application_name}",
        f"Raised by the IDP orchestrator for request `{req.id}` "
        f"(requested by {req.requested_by}).\n\nApproved and applied through the `platform` "
        "environment reviewers. Backstage tracks this as PLATFORM_PROVISIONING.",
    )
    req.platform = {**req.platform, "pr_number": pr.number, "pr_url": pr.url, "stacks": stacks}
    audit(s, req.id, ACTOR, "platform_pr_opened", pr=pr.url, files=sorted(files))


def h_dispatch(ctx: Context, s: Session, step: Step, req: Request) -> None:
    p = step.payload
    if p["repo"] == req.repository.get("name") and not req.repository.get("oidc_subject"):
        # Before the generated repository's first workflow: the subject its Azure federated credentials match.
        ctx.github.set_oidc_subject(p["repo"], OIDC_SUBJECT_CLAIMS)
        req.repository = {**req.repository, "oidc_subject": OIDC_SUBJECT_CLAIMS}
        audit(s, req.id, ACTOR, "oidc_subject_set", repo=p["repo"], claims=OIDC_SUBJECT_CLAIMS)
    ctx.github.dispatch_workflow(p["repo"], p["workflow"], p.get("ref", "main"), p["inputs"])
    record_run(req, stage=p["workflow"], run_id=None, url=None, status="dispatched")
    audit(s, req.id, ACTOR, "workflow_dispatched", repo=p["repo"], workflow=p["workflow"])


def h_release_rule(ctx: Context, s: Session, step: Step, req: Request) -> None:
    rule = req.protection_rule
    if not rule.get("callback_url") or rule.get("released_for") == step.payload["plan_hash"]:
        return
    ctx.github.review_protection_rule(
        rule["callback_url"],
        rule.get("environment", ""),
        step.payload["approve"],
        step.payload.get("comment", ""),
    )
    req.protection_rule = {**rule, "released_for": step.payload["plan_hash"]}


def app_values(settings: Settings, req: Request) -> dict[str, Any]:
    """Values the stack templates render with (outputs are empty until the infrastructure is applied)."""
    return {
        "app": req.application_name,
        "stack": req.stack,
        "description": req.spec.get("description", ""),
        "owner": req.owner,
        "environment": req.environment,
        "request_id": req.id,
        "org": settings.github_org,
        "platform_ref": settings.platform_repo_ref,
        "repo": _app_repo(req),
        "namespace": req.spec["namespace"]["name"],
        "endpoint_host": req.spec.get("endpoint_host", ""),
        "availability": req.spec.get("availability", {"tier": "standard"}),
        "runtime_capability": req.spec.get("runtime_capability", {"type": "none"}),
        "outputs": req.outputs or {},
        "resolved": req.validation.get("resolved", {}),
    }


def h_open_app_pr(ctx: Context, s: Session, step: Step, req: Request) -> None:
    if req.application.get("pr_number"):
        return
    # The starter source is already on main (first commit); unchanged files add nothing to the diff,
    # so the PR carries the CI/CD workflows and the Helm values filled with the infrastructure outputs.
    files = render_stack(ctx.settings.stack_templates_dir, req.stack, app_values(ctx.settings, req))
    branch = f"idp/app-{req.id}"
    repo = _app_repo(req)
    ctx.github.commit_files_on_branch(
        repo, "main", branch, files, f"feat: add {req.application_name} application ({req.stack})"
    )
    pr = ctx.github.open_pull_request(
        repo,
        branch,
        "main",
        f"Add {req.application_name} application ({req.stack})",
        f"Generated by IDP for request `{req.id}` after infrastructure was provisioned.\n\n"
        "The starter application (source, tests, Dockerfile, Compose, README) has been on `main` since the "
        "repository was created. This adds the CI/CD workflows and the Helm values filled with the "
        "infrastructure outputs. Merged automatically when required checks pass.",
    )
    req.application = {**req.application, "pr_number": pr.number, "pr_url": pr.url, "branch": branch}
    if req.state == State.INFRASTRUCTURE_READY:
        transition(s, req, State.APPLICATION_BUILDING, actor=ACTOR)


def h_merge_app_pr(ctx: Context, s: Session, step: Step, req: Request) -> None:
    number = req.application.get("pr_number")
    if not number:
        raise RetryLaterError("application PR not opened yet")
    pr = ctx.github.get_pull_request(_app_repo(req), number)
    if pr.merged:
        return
    if pr.mergeable_state not in ("clean", "has_hooks"):
        raise RetryLaterError(f"PR not mergeable yet ({pr.mergeable_state})")
    ctx.github.merge_pull_request(_app_repo(req), number, pr.head_sha)
    audit(s, req.id, ACTOR, "application_pr_merged", pr=pr.url)


def h_rerun(ctx: Context, s: Session, step: Step, req: Request) -> None:
    ctx.github.rerun_failed_jobs(step.payload["repo"], int(step.payload["run_id"]))
    audit(s, req.id, ACTOR, "workflow_rerun", repo=step.payload["repo"], run_id=step.payload["run_id"])


HANDLERS: dict[str, Callable[[Context, Session, Step, Request], None]] = {
    "VALIDATE": h_validate,
    "PLATFORM_REQUEST": h_platform_request,
    "DISPATCH": h_dispatch,
    "RELEASE_PROTECTION_RULE": h_release_rule,
    "OPEN_APP_PR": h_open_app_pr,
    "MERGE_APP_PR": h_merge_app_pr,
    "RERUN": h_rerun,
}


def run_step(ctx: Context, session: Session, step: Step) -> None:
    req = session.get(Request, step.request_id) if step.request_id else None
    if req is None:
        raise RuntimeError(f"step {step.id} has no request")
    ended = {State.FAILED, State.CANCELLED, State.CLEANED_UP}
    if req.state in ended and step.kind != "RELEASE_PROTECTION_RULE":
        return  # request ended: skip stale work (but still answer a held protection rule)
    HANDLERS[step.kind](ctx, session, step, req)


# =====================================================================================================
# Retry of a failed request
# =====================================================================================================


def _state_before_failure(s: Session, req: Request) -> State | None:
    events = s.scalars(
        select(AuditEvent)
        .where(AuditEvent.request_id == req.id, AuditEvent.action == "state_changed")
        .order_by(AuditEvent.id.desc())
    )
    for ev in events:
        if ev.details.get("to") == State.FAILED.value and ev.details.get("from"):
            return State(ev.details["from"])
    return None


def superseded_runs(req: Request) -> set[int]:
    """Workflow runs a retry replaced: the reconciler no longer judges the request by them."""
    return {int(i) for r in req.runs or [] for i in r.get("superseded", [])}


def retry_request(s: Session, req: Request, actor: str) -> str:
    """Resume a FAILED request where it stopped; returns what is retried.

    - an orchestrator step that ran out of attempts (e.g. a GitHub permission granted since): run it again;
    - validation or the infrastructure workflows: from validate again, or from a fresh plan (a failed
      apply never re-runs against its old plan; the new plan needs approval again);
    - the application's CI or deploy run: re-run its failed jobs.
    """
    previous = _state_before_failure(s, req)
    if req.state != State.FAILED or previous is None:
        raise RetryNotPossibleError(f"Request is {req.state}; only a failed request can be retried.")
    retried = select(func.count()).select_from(AuditEvent)
    attempt = 1 + (
        s.scalar(retried.where(AuditEvent.request_id == req.id, AuditEvent.action == "retried")) or 0
    )
    key = f":retry{attempt}"
    error = req.error or {}
    run = RUN_ID_RE.search(str(error.get("run_url") or ""))
    failed_runs = {
        int(r["run_id"])
        for r in req.runs or []
        if r.get("run_id") and str(r["run_id"]).isdigit() and r.get("status") in ("failure", "cancelled")
    }
    if run:
        failed_runs.add(int(run.group(1)))
    target = previous
    failed_steps = list(s.scalars(select(Step).where(Step.request_id == req.id, Step.status == "failed")))
    if failed_steps:
        for st in failed_steps:
            st.status, st.attempts, st.last_error, st.locked_until = "pending", 0, None, None
            st.run_after = datetime.now(UTC)
        what = ", ".join(sorted({st.kind.lower() for st in failed_steps}))
    elif previous in (State.REQUESTED, State.VALIDATING):
        enqueue(s, "VALIDATE", request_id=req.id, dedup_key=f"validate:{req.id}{key}")
        what = "validation"
    elif previous == State.REPOSITORY_CREATED:
        _dispatch(s, req, "terraform-validate.yml", {}, key=f"tf-validate:{req.id}{key}")
        what = "terraform-validate"
    elif previous in (State.INFRASTRUCTURE_PLANNED, State.AWAITING_APPROVAL, State.PROVISIONING):
        rule, plan_hash = req.protection_rule or {}, (req.plan or {}).get("hash")
        if rule.get("callback_url") and plan_hash and not rule.get("released_for"):
            # A held apply of the old plan: reject it so it doesn't wait forever.
            enqueue(
                s,
                "RELEASE_PROTECTION_RULE",
                request_id=req.id,
                dedup_key=f"release:{req.id}:{plan_hash}{key}",
                payload={"approve": False, "plan_hash": plan_hash, "comment": "Superseded by a retry."},
            )
        req.plan, req.approval = {}, {}
        _dispatch(s, req, "terraform-plan.yml", {"mode": "apply"}, key=f"plan:{req.id}{key}")
        target, what = State.REPOSITORY_CREATED, "terraform-plan (a new plan; approval needed again)"
    elif run and req.repository.get("name"):
        failed_runs.discard(int(run.group(1)))  # re-run in place: the same run id is judged again
        enqueue(
            s,
            "RERUN",
            request_id=req.id,
            dedup_key=f"rerun:{req.id}:{run.group(1)}{key}",
            payload={"repo": _app_repo(req), "run_id": run.group(1)},
        )
        what = f"failed jobs of run {run.group(1)}"
    elif previous == State.INFRASTRUCTURE_READY:
        enqueue(s, "OPEN_APP_PR", request_id=req.id, dedup_key=f"app-pr:{req.id}{key}")
        what = "open_app_pr"
    else:
        raise RetryNotPossibleError(
            f"A request that failed in {previous} can't be resumed; clean up and request again."
        )
    req.state, req.error = target.value, {}
    req.runs = [
        *(req.runs or []),
        {
            "stage": "retry",
            "run_id": None,
            "url": None,
            "status": "retried",
            "superseded": sorted(failed_runs),
            "at": datetime.now(UTC).isoformat(),
        },
    ][-50:]
    audit(s, req.id, actor, "retried", attempt=attempt, what=what, after=error.get("stage"))
    audit(
        s,
        req.id,
        actor,
        "state_changed",
        **{"from": State.FAILED.value, "to": target.value, "reason": f"retry: {what}"},
    )
    return what


# =====================================================================================================
# Inbound events (Actions callbacks and GitHub webhooks)
# =====================================================================================================


def on_callback(ctx: Context, s: Session, ev: InboxEvent) -> None:
    p = ev.payload
    req = s.get(Request, p.get("request_id"))
    if req is None:
        raise RuntimeError("callback for unknown request")
    stage, status, data = p["stage"], p["status"], p.get("data") or {}
    record_run(req, stage=stage, run_id=p.get("run_id"), url=p.get("run_url"), status=status)
    failed = status in ("failure", "cancelled")
    cleanup = req.state == State.CLEANUP_PENDING

    if failed:
        if cleanup:
            cleanup_step_failed(s, req, stage, p.get("run_url"))
        elif req.state in ACTIVE:
            fail(
                s,
                req,
                actor=ACTOR,
                stage=stage,
                message=data.get("message") or f"{stage} {status}",
                details={
                    "run_url": p.get("run_url"),
                    "created": data.get("created_resources", []),
                    # A failed deploy: which check failed and what the cluster confirms was restored.
                    **{k: data[k] for k in ("failure", "rollback", "restored", "diagnostics") if k in data},
                },
            )
        return

    match stage:
        case "validate" if status == "success":
            _dispatch(s, req, "terraform-plan.yml", {"mode": "apply"}, key=f"plan:{req.id}:{p.get('run_id')}")
        case "plan" if status == "success" and not cleanup:
            req.plan = {
                "hash": data["plan_hash"],
                "run_id": str(p.get("run_id")),
                "summary": data.get("summary", {}),
            }
            transition(s, req, State.INFRASTRUCTURE_PLANNED, actor=ACTOR)
            _dispatch(
                s,
                req,
                "terraform-apply.yml",
                {
                    "mode": "apply",
                    "plan_run_id": str(p.get("run_id")),
                    "expected_plan_hash": data["plan_hash"],
                },
                key=f"apply:{req.id}:{data['plan_hash']}:{p.get('run_id')}",
            )
        case "plan" if status == "success" and cleanup:
            req.plan = {
                "hash": data["plan_hash"],
                "run_id": str(p.get("run_id")),
                "summary": data.get("summary", {}),
                "mode": "destroy",
            }
            req.cleanup = {**req.cleanup, "stage": "destroy_planned"}
            _dispatch(
                s,
                req,
                "terraform-apply.yml",
                {
                    "mode": "destroy",
                    "plan_run_id": str(p.get("run_id")),
                    "expected_plan_hash": data["plan_hash"],
                },
                key=f"destroy-apply:{req.id}:{data['plan_hash']}",
            )
        case "apply" if status == "success" and not cleanup:
            req.outputs = {k: v for k, v in (data.get("outputs") or {}).items() if not k.endswith("_secret")}
            req.plan = {**req.plan, "applied": True}
            transition(s, req, State.INFRASTRUCTURE_READY, actor=ACTOR)
            enqueue(s, "OPEN_APP_PR", request_id=req.id, dedup_key=f"app-pr:{req.id}")
        case "apply" if status == "success" and cleanup:
            req.cleanup = {**req.cleanup, "stage": "done"}
            transition(s, req, State.CLEANED_UP, actor=ACTOR)
        case "ci" if status == "success":
            req.application = {**req.application, "image": data.get("image"), "scan": data.get("scan")}
        case "deploy" if status == "started":
            if req.state == State.APPLICATION_BUILDING:
                transition(s, req, State.DEPLOYING, actor=ACTOR)
        case "deploy" if status == "success":
            req.deployment = {
                **req.deployment,
                **data,
                "run_url": p.get("run_url"),
                "deployed_at": datetime.now(UTC).isoformat(),
            }
            if req.state == State.APPLICATION_BUILDING:
                transition(s, req, State.DEPLOYING, actor=ACTOR)
            if req.state == State.DEPLOYING:  # later deploys of a SUCCEEDED request only update the record
                transition(s, req, State.SUCCEEDED, actor=ACTOR)
        case "uninstall" if status == "success" and cleanup:
            req.cleanup = {**req.cleanup, "stage": "uninstalled"}
            attempt = int(req.cleanup.get("attempt", 1))
            _dispatch(
                s,
                req,
                "terraform-plan.yml",
                {"mode": "destroy"},
                key=f"destroy-plan-after-uninstall:{req.id}:{attempt}",
            )
        case "platform_apply" if status == "success":
            req.ready_for_repository = True
            req.platform = {**req.platform, "applied": True, "apply_run": p.get("run_url")}
            audit(s, req.id, ACTOR, "platform_applied", run=p.get("run_url"))
        case _:
            log.info("ignored callback stage=%s status=%s", stage, status)


def _request_for_repo(s: Session, repo_name: str) -> Request | None:
    return s.scalar(
        select(Request)
        .where(
            Request.repository["name"].as_string() == repo_name,
            Request.state.notin_([State.CLEANED_UP.value]),
        )
        .order_by(Request.created_at.desc())
    )


def on_webhook(ctx: Context, s: Session, ev: InboxEvent) -> None:
    p = ev.payload
    repo = (p.get("repository") or {}).get("name", "")

    if ev.event_type == "deployment_protection_rule" and p.get("action") == "requested":
        req = _request_for_repo(s, repo)
        if req is None or p.get("environment") != ctx.settings.infra_environment:
            return
        req.protection_rule = {"callback_url": p["deployment_callback_url"], "environment": p["environment"]}
        if req.state == State.INFRASTRUCTURE_PLANNED:
            transition(s, req, State.AWAITING_APPROVAL, actor=ACTOR)
        elif req.state == State.CLEANUP_PENDING:
            req.cleanup = {**req.cleanup, "stage": "awaiting_approval"}
            s.add(
                OutboxMessage(
                    kind="notification",
                    payload={
                        "request_id": req.id,
                        "application": req.application_name,
                        "audience": "approvers",
                        "owner": req.owner,
                        "requested_by": req.requested_by,
                        "state": "CLEANUP_PENDING",
                        "title": f"Approval needed (destroy): {req.application_name} ({req.environment})",
                    },
                )
            )
        return

    if (
        ev.event_type == "pull_request"
        and p.get("action") == "closed"
        and (p.get("pull_request") or {}).get("merged")
    ):
        head = p["pull_request"]["head"]["ref"]
        if repo == ctx.settings.platform_repo and head.startswith("idp/platform-"):
            req = s.get(Request, head.removeprefix("idp/platform-"))
            if req and req.state == State.PLATFORM_PROVISIONING:
                for stack in req.platform.get("stacks", []):
                    _dispatch(
                        s,
                        req,
                        "platform-apply.yml",
                        {"stack": stack},
                        key=f"platform-apply:{req.id}:{stack}",
                        repo=ctx.settings.platform_repo,
                    )
        return

    if ev.event_type == "workflow_run" and p.get("action") == "completed":
        run = p.get("workflow_run") or {}
        branch = run.get("head_branch") or ""
        if (
            run.get("conclusion") == "success"
            and branch.startswith("idp/app-")
            and run.get("event") == "pull_request"
        ):
            req = s.get(Request, branch.removeprefix("idp/app-"))
            if req and req.state == State.APPLICATION_BUILDING:
                enqueue(s, "MERGE_APP_PR", request_id=req.id, dedup_key=f"merge:{req.id}:{run.get('id')}")
            return
        if run.get("conclusion") in ("failure", "timed_out", "startup_failure"):
            # Fallback when a job died before it could send its own failure callback.
            match = UUID_RE.search(run.get("display_title") or "") or UUID_RE.search(branch)
            req = s.get(Request, match.group(0)) if match else None
            if req and req.state == State.CLEANUP_PENDING:
                cleanup_step_failed(s, req, run.get("name", "workflow"), run.get("html_url"))
            elif req and req.state in ACTIVE:
                fail(
                    s,
                    req,
                    actor=ACTOR,
                    stage=run.get("name", "workflow"),
                    message=f"Workflow '{run.get('name')}' failed.",
                    details={"run_url": run.get("html_url")},
                )


def process_inbox_event(ctx: Context, session: Session, ev: InboxEvent) -> None:
    if ev.source == "actions_callback":
        on_callback(ctx, session, ev)
    else:
        on_webhook(ctx, session, ev)
    ev.processed_at = datetime.now(UTC)


# =====================================================================================================
# Outbox delivery
# =====================================================================================================


def deliver_outbox_message(ctx: Context, msg: OutboxMessage) -> None:
    p = msg.payload
    if msg.kind == "catalog_unregister":
        ctx.backstage.unregister_component(p["application"])
        return
    if p.get("audience") == "approvers":
        recipients = [ctx.settings.approver_group]
        link = "/idp/approvals"
        severity = "high"
    else:
        recipients = sorted(r for r in {p.get("owner"), p.get("requested_by")} if r)
        link = f"/catalog/default/component/{p.get('application', '')}"
        severity = "critical" if p.get("state") == "FAILED" else "normal"
    description = p.get("error") or f"Request {p.get('request_id')} is now {p.get('state')}."
    ctx.backstage.notify(recipients, p["title"], description, link, severity)
