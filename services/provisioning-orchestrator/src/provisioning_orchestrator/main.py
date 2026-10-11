"""FastAPI application. The API only reads and writes the database; all slow work (GitHub, discovery,
templating) happens in the worker via queued steps."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request as HttpRequest, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sportify_common.auth import AuthSettings, Caller, authenticate, require_caller, require_user
from sportify_common.jwt_verify import TokenVerificationError, github_actions_verifier
from sportify_common.logging import configure_logging
from sportify_common.secrets import read_secret_file
from sportify_common.telemetry import configure_tracing

from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.db import make_engine, make_session_factory
from provisioning_orchestrator.models import InboxEvent, Request
from provisioning_orchestrator.schemas import (
    ApprovalDecision,
    CallbackBody,
    RepositoryRecord,
    RequestCreate,
    RequestOut,
)
from provisioning_orchestrator.service import audit, enqueue, transition
from provisioning_orchestrator.states import ACTIVE, CANCELLABLE, CLEANABLE, State
from provisioning_orchestrator.views import to_out


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": code, "message": message})


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": code, "message": message})


def verify_github_signature(body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    secrets = [read_secret_file("ORCHESTRATOR_GITHUB_WEBHOOK_SECRET_FILE")]
    # During rotation the previous secret is accepted too (docs/security/secret-management.md §6.2).
    if previous := read_secret_file("ORCHESTRATOR_GITHUB_WEBHOOK_SECRET_PREVIOUS_FILE", required=False):
        secrets.append(previous)
    for secret in secrets:
        expected = "sha256=" + hmac.new((secret or "").encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True
    return False


def create_app(settings: Settings | None = None, sessions: sessionmaker[Session] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging("provisioning-orchestrator", settings.log_level)
    configure_tracing("provisioning-orchestrator")
    if sessions is None:
        sessions = make_session_factory(make_engine(settings.database_url, entra_auth=settings.database_entra_auth))

    app = FastAPI(title="provisioning-orchestrator", version="1.0.0")

    def db() -> Session:  # type: ignore[misc]
        with sessions() as s:
            yield s

    DB = Annotated[Session, Depends(db)]
    User = Annotated[Caller, Depends(require_user)]
    Svc = Annotated[Caller, Depends(require_caller)]

    def load(s: Session, request_id: str, *, lock: bool = False) -> Request:
        stmt = select(Request).where(Request.id == request_id)
        if lock:
            stmt = stmt.with_for_update()
        req = s.scalar(stmt)
        if req is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="request not found")
        return req

    def out(req: Request) -> RequestOut:
        return to_out(req, settings.backstage_base_url, settings.github_org)

    # ---------------- health ----------------
    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz(s: DB) -> JSONResponse:
        try:
            s.execute(text("SELECT 1"))
            return JSONResponse({"status": "ready"})
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "not_ready"}, status_code=503)

    # ---------------- requests ----------------
    @app.post("/v1/requests", response_model=RequestOut, status_code=201)
    def submit(body: RequestCreate, caller: User, s: DB) -> RequestOut:
        user = caller.user
        assert user is not None
        existing = s.scalar(select(Request).where(Request.idempotency_key == body.idempotency_key))
        if existing:  # duplicate submission (retry, double click): return the same request
            return out(existing)
        if not user.in_group(body.owner):
            raise _forbidden("not_owner_member", "You must be a member of the owning team.")
        active = s.scalar(select(Request).where(
            Request.application_name == body.application_name,
            Request.environment == body.environment,
            Request.state.in_([st.value for st in ACTIVE]),
        ))
        if active:
            raise _conflict("duplicate_application", f"An active request for '{body.application_name}' "
                                                     f"in {body.environment} already exists ({active.id}).")
        req = Request(
            idempotency_key=body.idempotency_key, application_name=body.application_name,
            environment=body.environment, owner=body.owner, stack=body.stack, requested_by=user.user_ref,
            state=State.REQUESTED.value, spec=body.model_dump(exclude={"idempotency_key"}),
        )
        try:
            s.add(req)
            s.flush()
            audit(s, req.id, user.user_ref, "requested", application=req.application_name,
                  environment=req.environment, availability=body.availability.model_dump())
            enqueue(s, "VALIDATE", request_id=req.id, dedup_key=f"validate:{req.id}")
            s.commit()
        except IntegrityError:
            s.rollback()
            existing = s.scalar(select(Request).where(Request.idempotency_key == body.idempotency_key))
            if existing:
                return out(existing)
            raise
        return out(req)

    @app.get("/v1/requests/{request_id}", response_model=RequestOut)
    def get_request(request_id: str, _: Svc, s: DB) -> RequestOut:
        return out(load(s, request_id))

    @app.get("/v1/requests", response_model=list[RequestOut])
    def list_requests(_: Svc, s: DB, application: str | None = None, limit: int = 20) -> list[RequestOut]:
        stmt = select(Request).order_by(Request.created_at.desc()).limit(min(limit, 100))
        if application:
            stmt = stmt.where(Request.application_name == application)
        return [out(r) for r in s.scalars(stmt)]

    @app.post("/v1/requests/{request_id}/repository", response_model=RequestOut)
    def record_repository(request_id: str, body: RepositoryRecord, caller: Svc, s: DB) -> RequestOut:
        req = load(s, request_id, lock=True)
        if req.repository.get("name") == body.name:
            return out(req)  # idempotent
        if req.state not in (State.VALIDATING, State.PLATFORM_PROVISIONING) or not req.ready_for_repository:
            raise _conflict("not_ready", f"Request is {req.state}; repository can't be recorded yet.")
        req.repository = body.model_dump()
        transition(s, req, State.REPOSITORY_CREATED, actor=caller.subject)
        audit(s, req.id, caller.subject, "repository_created", url=body.url)
        enqueue(s, "DISPATCH", request_id=req.id, dedup_key=f"tf-validate:{req.id}", payload={
            "repo": body.name, "workflow": "terraform-validate.yml",
            "inputs": {"request_id": req.id}})
        s.commit()
        return out(req)

    # ---------------- approvals ----------------
    @app.get("/v1/approvals", response_model=list[RequestOut])
    def pending_approvals(caller: User, s: DB) -> list[RequestOut]:
        assert caller.user is not None
        if not caller.user.in_group(settings.approver_group):
            return []
        rows = s.scalars(select(Request).where(Request.state.in_([State.AWAITING_APPROVAL.value,
                                                                 State.CLEANUP_PENDING.value])))
        return [out(r) for r in rows
                if r.state == State.AWAITING_APPROVAL or r.cleanup.get("stage") == "awaiting_approval"]

    @app.post("/v1/requests/{request_id}/approval", response_model=RequestOut)
    def decide(request_id: str, body: ApprovalDecision, caller: User, s: DB) -> RequestOut:
        user = caller.user
        assert user is not None
        req = load(s, request_id, lock=True)
        if not user.in_group(settings.approver_group):
            raise _forbidden("not_approver", "You are not an approver for this environment.")
        if user.user_ref == req.requested_by:
            raise _forbidden("separation_of_duties", "You can't approve your own request.")
        destroy = req.state == State.CLEANUP_PENDING and req.cleanup.get("stage") == "awaiting_approval"
        if req.state != State.AWAITING_APPROVAL and not destroy:
            raise _conflict("not_awaiting_approval", f"Request is {req.state}.")
        if req.approval.get("hash") == body.plan_hash:
            raise _conflict("already_decided", "This plan has already been decided.")
        if req.plan.get("hash") != body.plan_hash:
            raise _conflict("plan_changed", "The plan changed since you reviewed it; review the new plan.")
        approve = body.decision == "approve"
        req.approval = {"decision": body.decision, "by": user.user_ref, "hash": body.plan_hash,
                        "comment": body.comment, "mode": req.plan.get("mode", "apply")}
        audit(s, req.id, user.user_ref, "approval_decided", decision=body.decision, plan_hash=body.plan_hash,
              comment=body.comment, summary=req.plan.get("summary"))
        enqueue(s, "RELEASE_PROTECTION_RULE", request_id=req.id,
                dedup_key=f"release:{req.id}:{body.plan_hash}",
                payload={"approve": approve, "plan_hash": body.plan_hash,
                         "comment": f"{body.decision} by {user.user_ref} in Backstage. {body.comment}"})
        if destroy:
            req.cleanup = {**req.cleanup, "stage": "destroying" if approve else "rejected"}
        elif approve:
            transition(s, req, State.PROVISIONING, actor=user.user_ref)
        else:
            transition(s, req, State.CANCELLED, actor=user.user_ref, reason="plan rejected")
        s.commit()
        return out(req)

    # ---------------- cancel / cleanup ----------------
    def _may_manage(user_groups: Caller, req: Request) -> bool:
        u = user_groups.user
        return bool(u and (u.user_ref == req.requested_by or u.in_group(req.owner)
                           or u.in_group(settings.approver_group)))

    @app.post("/v1/requests/{request_id}/cancel", response_model=RequestOut)
    def cancel(request_id: str, caller: User, s: DB) -> RequestOut:
        req = load(s, request_id, lock=True)
        if not _may_manage(caller, req):
            raise _forbidden("not_allowed", "Only the requester, owning team or approvers can cancel.")
        if req.state not in CANCELLABLE:
            raise _conflict("not_cancellable", f"Request is {req.state}; it can't be cancelled now.")
        if req.state == State.AWAITING_APPROVAL and req.plan.get("hash"):
            enqueue(s, "RELEASE_PROTECTION_RULE", request_id=req.id,
                    dedup_key=f"release:{req.id}:{req.plan['hash']}",
                    payload={"approve": False, "plan_hash": req.plan["hash"], "comment": "Request cancelled."})
        transition(s, req, State.CANCELLED, actor=caller.user.user_ref if caller.user else caller.subject)
        s.commit()
        return out(req)

    @app.post("/v1/requests/{request_id}/cleanup", response_model=RequestOut)
    def cleanup(request_id: str, caller: User, s: DB) -> RequestOut:
        req = load(s, request_id, lock=True)
        if not _may_manage(caller, req):
            raise _forbidden("not_allowed", "Only the requester, owning team or approvers can clean up.")
        if req.state == State.CLEANUP_PENDING:
            return out(req)
        if req.state not in CLEANABLE:
            raise _conflict("not_cleanable", f"Request is {req.state}.")
        actor = caller.user.user_ref if caller.user else caller.subject
        transition(s, req, State.CLEANUP_PENDING, actor=actor)
        repo = req.repository.get("name")
        if not repo:
            req.cleanup = {"stage": "done", "note": "nothing was created"}
            transition(s, req, State.CLEANED_UP, actor=actor)
        elif req.application.get("image") or req.deployment:
            req.cleanup = {"stage": "uninstalling"}
            enqueue(s, "DISPATCH", request_id=req.id, dedup_key=f"uninstall:{req.id}", payload={
                "repo": repo, "workflow": "application-deploy.yml",
                "inputs": {"request_id": req.id, "action": "uninstall"}})
        else:
            req.cleanup = {"stage": "planning_destroy"}
            enqueue(s, "DISPATCH", request_id=req.id, dedup_key=f"destroy-plan:{req.id}", payload={
                "repo": repo, "workflow": "terraform-plan.yml",
                "inputs": {"request_id": req.id, "mode": "destroy"}})
        s.commit()
        return out(req)

    # ---------------- inbound from GitHub ----------------
    @app.post("/v1/webhooks/github", status_code=202)
    async def github_webhook(
        request: HttpRequest, s: DB,
        x_github_event: Annotated[str, Header()],
        x_github_delivery: Annotated[str, Header()],
        x_hub_signature_256: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        body = await request.body()
        if not verify_github_signature(body, x_hub_signature_256):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid signature")
        try:
            s.add(InboxEvent(source="github_webhook", delivery_id=x_github_delivery,
                             event_type=x_github_event, payload=await request.json()))
            s.commit()
        except IntegrityError:
            s.rollback()
            return {"status": "duplicate"}
        return {"status": "accepted"}

    @app.post("/v1/callbacks/actions", status_code=202)
    def actions_callback(body: CallbackBody, s: DB,
                         authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing token")
        token = authorization.split(" ", 1)[1]
        auth = AuthSettings.from_env()
        if auth.mode == "static":  # local development only
            authenticate(auth, authorization)
            claims = {"repository": "", "run_id": str(body.run_id or 0), "run_attempt": "1"}
        else:
            try:
                claims = github_actions_verifier(settings.callback_audience).verify(token)
            except TokenVerificationError as exc:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
        req = load(s, body.request_id)
        if auth.mode != "static":
            expected_repo = (settings.platform_repo if body.stage == "platform_apply"
                             else req.repository.get("name", ""))
            if claims.get("repository") != f"{settings.github_org}/{expected_repo}":
                raise _forbidden("wrong_repository", "Callback is not from the request's repository.")
            if claims.get("repository_owner") != settings.github_org:
                raise _forbidden("wrong_owner", "Callback is not from the platform organisation.")
        delivery = f"{claims.get('run_id')}:{claims.get('run_attempt')}:{body.stage}:{body.status}"
        try:
            s.add(InboxEvent(source="actions_callback", delivery_id=delivery, event_type=body.stage,
                             payload=body.model_dump()))
            s.commit()
        except IntegrityError:
            s.rollback()
            return {"status": "duplicate"}
        return {"status": "accepted"}

    return app


def run() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8002")))  # noqa: S104
