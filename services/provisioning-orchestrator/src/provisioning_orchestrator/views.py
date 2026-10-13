"""Build API views: separate outcomes ("honest status") and the shared URLs."""

from __future__ import annotations

from provisioning_orchestrator.models import Request
from provisioning_orchestrator.schemas import Outcome, RequestOut
from provisioning_orchestrator.states import State

_ORDER = [
    State.REQUESTED,
    State.VALIDATING,
    State.PLATFORM_PROVISIONING,
    State.REPOSITORY_CREATED,
    State.INFRASTRUCTURE_PLANNED,
    State.AWAITING_APPROVAL,
    State.PROVISIONING,
    State.INFRASTRUCTURE_READY,
    State.APPLICATION_BUILDING,
    State.DEPLOYING,
    State.SUCCEEDED,
]
_RANK = {s: i for i, s in enumerate(_ORDER)}

_OUTCOMES: list[tuple[str, State]] = [
    ("Request validated", State.REPOSITORY_CREATED),
    ("Repository created", State.REPOSITORY_CREATED),
    ("Infrastructure provisioned", State.INFRASTRUCTURE_READY),
    ("Application built", State.DEPLOYING),
    ("Deployed", State.SUCCEEDED),
]

_STAGE_OF_OUTCOME = {
    "Request validated": {"validate"},
    "Repository created": {"repository"},
    "Infrastructure provisioned": {"plan", "apply", "platform_apply"},
    "Application built": {"ci", "application"},
    "Deployed": {"deploy"},
}


def outcomes(req: Request) -> list[Outcome]:
    state = State(req.state)
    failed_stage = (req.error or {}).get("stage")
    # Highest progress reached, including before a failure (from run history and stored data).
    reached = _RANK.get(state, -1)
    if state in {State.FAILED, State.CANCELLED, State.CLEANUP_PENDING, State.CLEANED_UP}:
        reached = -1
        if req.repository.get("name"):
            reached = _RANK[State.REPOSITORY_CREATED]
        if req.plan.get("applied") and req.plan.get("mode", "apply") == "apply":
            reached = _RANK[State.INFRASTRUCTURE_READY]
        if req.application.get("image"):
            reached = _RANK[State.DEPLOYING]
        if req.deployment.get("endpoint"):
            reached = _RANK[State.SUCCEEDED]
    out = []
    for name, threshold in _OUTCOMES:
        if reached >= _RANK[threshold]:
            status = "succeeded"
        elif state == State.FAILED and failed_stage in _STAGE_OF_OUTCOME[name]:
            status = "failed"
        elif state in {State.FAILED, State.CANCELLED}:
            status = "skipped"
        else:
            status = "pending"
        out.append(Outcome(name=name, status=status))  # type: ignore[arg-type]
    return out


def urls(req: Request, backstage_base: str, org: str) -> dict[str, str]:
    u: dict[str, str] = {}
    host = req.deployment.get("endpoint") or req.spec.get("endpoint_host")
    if req.deployment.get("endpoint") and host:
        base = host if str(host).startswith("http") else f"https://{host}"
        u.update({"application": base, "api_docs": f"{base}/docs", "health": f"{base}/health/ready"})
    if req.repository.get("url"):
        u["repository"] = req.repository["url"]
        u["workflow_runs"] = f"{req.repository['url']}/actions"
    if req.application.get("image"):
        u["image"] = req.application["image"]
    if req.application.get("pr_url"):
        u["application_pr"] = req.application["pr_url"]
    if req.platform.get("pr_url"):
        u["platform_pr"] = req.platform["pr_url"]
    rg_id = (req.validation.get("resolved") or {}).get("resource_group_id")
    if rg_id:
        u["azure_resource_group"] = f"https://portal.azure.com/#resource{rg_id}"
    u["backstage"] = f"{backstage_base}/catalog/default/component/{req.application_name}"
    return u


def to_out(req: Request, backstage_base: str, org: str) -> RequestOut:
    validation = req.validation or {}
    return RequestOut(
        id=req.id,
        state=req.state,
        application_name=req.application_name,
        environment=req.environment,
        owner=req.owner,
        stack=req.stack,
        requested_by=req.requested_by,
        ready_for_repository=req.ready_for_repository,
        endpoint_host=req.spec.get("endpoint_host", ""),
        validation={k: validation.get(k) for k in ("valid", "errors", "warnings", "platform_changes")},
        repository=req.repository,
        platform=req.platform,
        plan={k: req.plan.get(k) for k in ("hash", "summary", "mode")},
        approval=req.approval,
        application=req.application,
        deployment=req.deployment,
        cleanup=req.cleanup,
        availability=req.spec.get("availability", {}),
        error=req.error,
        runs=req.runs or [],
        outcomes=outcomes(req),
        urls=urls(req, backstage_base, org),
        created_at=req.created_at,
        updated_at=req.updated_at,
    )
