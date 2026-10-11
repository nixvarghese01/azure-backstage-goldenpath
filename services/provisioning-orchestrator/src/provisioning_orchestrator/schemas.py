"""API schemas (OpenAPI contract for the Backstage bridge)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Mode = Literal["new", "existing"]


class Selection(BaseModel):
    mode: Mode
    id: str | None = None
    name: str | None = None


class RuntimeCapability(BaseModel):
    type: Literal["storage", "keyvault", "none"] = "storage"
    mode: Mode = "existing"
    id: str | None = None
    name: str | None = None


class Availability(BaseModel):
    tier: Literal["standard", "ha"] = "standard"
    reason: str | None = None
    justification: str | None = Field(default=None, max_length=500)
    slo_target: str | None = None


class RequestCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    application_name: str = Field(min_length=3, max_length=64)
    description: str = Field(default="", max_length=300)
    owner: str = Field(description="Owning group entity ref, e.g. group:default/team-orders")
    environment: str = "dev"
    region: str
    stack: str = "nestjs"
    subscription: Selection
    resource_group: Selection
    aks_cluster: Selection
    container_registry: Selection
    namespace: Selection
    runtime_capability: RuntimeCapability = Field(default_factory=RuntimeCapability)
    availability: Availability = Field(default_factory=Availability)
    endpoint_host: str = Field(default="", max_length=253)
    repository_visibility: Literal["public", "private"] = "public"


class RepositoryRecord(BaseModel):
    owner: str
    name: str
    url: str


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    plan_hash: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    comment: str = Field(default="", max_length=1000)


class CallbackBody(BaseModel):
    request_id: str
    stage: Literal["validate", "plan", "apply", "ci", "deploy", "uninstall", "platform_apply"]
    status: Literal["started", "success", "failure", "cancelled"]
    run_id: int | None = None
    run_url: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Outcome(BaseModel):
    name: str
    status: Literal["pending", "succeeded", "failed", "skipped"]


class RequestOut(BaseModel):
    id: str
    state: str
    application_name: str
    environment: str
    owner: str
    stack: str
    requested_by: str
    ready_for_repository: bool
    validation: dict[str, Any]
    repository: dict[str, Any]
    platform: dict[str, Any]
    plan: dict[str, Any]
    approval: dict[str, Any]
    application: dict[str, Any]
    deployment: dict[str, Any]
    cleanup: dict[str, Any]
    availability: dict[str, Any]
    error: dict[str, Any]
    runs: list[dict[str, Any]]
    outcomes: list[Outcome]
    urls: dict[str, str]
    created_at: datetime
    updated_at: datetime
