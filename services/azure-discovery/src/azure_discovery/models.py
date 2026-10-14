"""API models (the OpenAPI document generated from these is the contract for the Backstage bridge)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["new", "existing"]


class Tenant(BaseModel):
    id: str
    name: str
    default_domain: str | None = None


class ManagementGroup(BaseModel):
    """A management group. ``parent_id`` is None for the Tenant Root Group (its id is the tenant id)."""

    id: str
    name: str
    tenant_id: str
    parent_id: str | None = None


class ManagementGroupOut(ManagementGroup):
    # Ancestor names from the Tenant Root Group down to this group, for "Platform / Corp" style labels.
    path: list[str] = Field(default_factory=list)
    depth: int = 0


class Subscription(BaseModel):
    id: str
    name: str
    state: str
    quota_id: str | None = None
    tenant_id: str | None = None
    # Management group ids from the direct parent up to the Tenant Root Group; empty when unknown.
    management_groups: list[str] = Field(default_factory=list)


class ResourceGroup(BaseModel):
    id: str
    name: str
    location: str


class NodePool(BaseModel):
    name: str
    mode: str
    vm_size: str
    count: int
    zones: list[str] = Field(default_factory=list)


class AksCluster(BaseModel):
    id: str
    name: str
    resource_group: str
    location: str
    kubernetes_version: str | None = None
    oidc_issuer_enabled: bool = False
    workload_identity_enabled: bool = False
    node_pools: list[NodePool] = Field(default_factory=list)

    @property
    def zones_spanned(self) -> int:
        """Max zones covered by any user (or, failing that, system) pool with >= 2 nodes."""
        pools = [p for p in self.node_pools if p.mode.lower() == "user"] or self.node_pools
        return max((len(set(p.zones)) for p in pools if p.count >= 2), default=0)


class AksClusterOut(AksCluster):
    zones: int
    ha_eligible: bool
    # Gateway base domain from the allowlist; applications default to <name>.<base_domain>.
    base_domain: str | None = None


class ContainerRegistry(BaseModel):
    id: str
    name: str
    resource_group: str
    location: str
    sku: str
    login_server: str


class DataResource(BaseModel):
    id: str
    name: str
    type: str
    resource_group: str
    location: str
    sku: str | None = None


class CapabilityOption(BaseModel):
    available: bool
    reason: str | None = None


class Capabilities(BaseModel):
    subscription_id: str
    quota_id: str | None
    create_new: dict[str, CapabilityOption]
    regional_vcpus: dict[str, int] | None = None


# ---------------- validation ----------------


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
    justification: str | None = None
    slo_target: str | None = None


class ValidationRequest(BaseModel):
    application_name: str
    environment: str
    region: str
    # Where the subscription was picked in the CAF hierarchy; checked against the live hierarchy.
    tenant_id: str | None = None
    management_group: str | None = None
    subscription: Selection
    resource_group: Selection
    aks_cluster: Selection
    container_registry: Selection
    namespace: Selection
    runtime_capability: RuntimeCapability = Field(default_factory=RuntimeCapability)
    availability: Availability = Field(default_factory=Availability)
    stack: str = "nestjs"
    # Empty = <application_name>.<gateway base_domain> of the selected cluster.
    endpoint_host: str = ""


class Finding(BaseModel):
    field: str
    code: str
    message: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    platform_changes: list[str] = Field(
        default_factory=list,
        description=(
            "Platform-level resources to create first (subscription, aks_cluster, container_registry)"
        ),
    )
    resolved: dict[str, str] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    code: Literal["permission_denied", "not_found", "throttled", "unavailable", "not_allowlisted"]
    message: str
