"""FastAPI application for azure-discovery (read-only)."""

# Route dependency aliases live inside create_app, so keep annotations evaluable in that scope.
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from idp_common.auth import Caller, require_caller
from idp_common.logging import configure_logging
from idp_common.telemetry import configure_tracing

from azure_discovery.cache import TtlCache
from azure_discovery.capabilities import compute_capabilities
from azure_discovery.config import Settings
from azure_discovery.inventory.base import AzureInventory, InventoryError
from azure_discovery.models import (
    AksClusterOut,
    Capabilities,
    ContainerRegistry,
    DataResource,
    ManagementGroup,
    ManagementGroupOut,
    ResourceGroup,
    Subscription,
    Tenant,
    ValidationRequest,
    ValidationResult,
)
from azure_discovery.policy import Allowlist, load_allowlist
from azure_discovery.validation import validate_request

_STATUS = {"permission_denied": 403, "not_found": 404, "throttled": 503, "unavailable": 503}


def create_app(
    settings: Settings | None = None,
    inventory: AzureInventory | None = None,
    policy: Allowlist | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging("azure-discovery", settings.log_level)
    configure_tracing("azure-discovery")

    if inventory is None:
        if settings.azure_mode == "mock":
            from azure_discovery.inventory.mock import MockInventory

            inventory = MockInventory()
        else:
            from azure_discovery.inventory.sdk import SdkInventory

            inventory = SdkInventory()
    policy = policy or load_allowlist(settings.policy_file)
    cache = TtlCache(settings.cache_ttl_seconds)

    app = FastAPI(
        title="azure-discovery",
        version="1.0.0",
        description="Read-only Azure discovery for Internal Developer Portal",
    )
    app.state.inventory = inventory
    app.state.policy = policy
    app.state.cache = cache

    @app.exception_handler(InventoryError)
    async def _inventory_error(_: Request, exc: InventoryError) -> JSONResponse:
        return JSONResponse(
            status_code=_STATUS.get(exc.code, 503), content={"code": exc.code, "message": str(exc)}
        )

    Auth = Annotated[Caller, Depends(require_caller)]

    def _allowed_sub(sub_id: str, env: str | None) -> None:
        entry = policy.subscription(sub_id)
        if not entry or (env and env not in entry.environments):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "not_allowlisted", "message": "Subscription is not approved."},
            )

    # ---------------- health ----------------
    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz() -> JSONResponse:
        ok = inventory.can_acquire_token()
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ready" if ok else "not_ready", "azure_credential": ok},
        )

    # ---------------- discovery: tenant -> management groups -> subscriptions ----------------
    def _approved_subscriptions(environment: str | None) -> list[Subscription]:
        """Enabled, allowlisted subscriptions in the approved tenant and landing zone scope."""
        subs = cache.get_or_load("subs", inventory.list_subscriptions)
        out = []
        for s in subs:
            entry = policy.subscription(s.id)
            if (
                entry
                and s.state.lower() == "enabled"
                and (environment is None or environment in entry.environments)
                and policy.tenant_allowed(s.tenant_id)
                and policy.in_application_scope(s.management_groups)
            ):
                out.append(s)
        return out

    @app.get("/v1/tenants", response_model=list[Tenant])
    def tenants(_: Auth, environment: str | None = None) -> list[Tenant]:
        used = {(s.tenant_id or "").lower() for s in _approved_subscriptions(environment)}
        return [
            t
            for t in cache.get_or_load("tenants", inventory.list_tenants)
            if t.id.lower() in used and policy.tenant_allowed(t.id)
        ]

    @app.get("/v1/management-groups", response_model=list[ManagementGroupOut])
    def management_groups(
        _: Auth, tenant_id: Annotated[str, Query()], environment: str | None = None
    ) -> list[ManagementGroupOut]:
        """The management group tree, pruned to groups that contain an approved subscription.

        Depth-first from the Tenant Root Group. Without management group access (or a tenant with
        no groups) this is just the Tenant Root Group, so the form always has one choice.
        """
        groups = {
            g.id.lower(): g
            for g in cache.get_or_load("mgs", inventory.list_management_groups)
            if g.tenant_id.lower() == tenant_id.lower()
        }
        groups.setdefault(
            tenant_id.lower(), ManagementGroup(id=tenant_id, name="Tenant Root Group", tenant_id=tenant_id)
        )
        keep = {tenant_id.lower()}
        for s in _approved_subscriptions(environment):
            if (s.tenant_id or "").lower() == tenant_id.lower():
                keep.update(m.lower() for m in s.management_groups if m.lower() in groups)
        children: dict[str, list[ManagementGroup]] = {}
        for g in groups.values():
            if g.id.lower() in keep and g.parent_id:
                children.setdefault(g.parent_id.lower(), []).append(g)
        out: list[ManagementGroupOut] = []

        def walk(g: ManagementGroup, path: list[str]) -> None:
            here = [*path, g.name]
            out.append(ManagementGroupOut(**g.model_dump(), path=here, depth=len(path)))
            for child in sorted(children.get(g.id.lower(), []), key=lambda c: c.name.lower()):
                walk(child, here)

        walk(groups[tenant_id.lower()], [])
        return out

    @app.get("/v1/subscriptions", response_model=list[Subscription])
    def subscriptions(
        _: Auth,
        environment: str | None = None,
        tenant_id: str | None = None,
        management_group: str | None = None,
    ) -> list[Subscription]:
        """Approved subscriptions, optionally limited to a tenant and a management group's subtree."""
        out = []
        for s in _approved_subscriptions(environment):
            if tenant_id and (s.tenant_id or "").lower() != tenant_id.lower():
                continue
            # The Tenant Root Group's id is the tenant id: every subscription in the tenant is below it.
            under_root = management_group and tenant_id and management_group.lower() == tenant_id.lower()
            if (
                management_group
                and not under_root
                and management_group.lower() not in {m.lower() for m in s.management_groups}
            ):
                continue
            out.append(s)
        return out

    @app.get("/v1/subscriptions/{sub_id}/capabilities", response_model=Capabilities)
    def capabilities(_: Auth, sub_id: str, region: Annotated[str, Query()]) -> Capabilities:
        _allowed_sub(sub_id, None)
        if not policy.region_allowed(region):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="region not allowed")
        return compute_capabilities(sub_id, region, inventory, policy)

    @app.get("/v1/subscriptions/{sub_id}/resource-groups", response_model=list[ResourceGroup])
    def resource_groups(_: Auth, sub_id: str, environment: str | None = None) -> list[ResourceGroup]:
        _allowed_sub(sub_id, environment)
        groups = cache.get_or_load(f"rg:{sub_id}", lambda: inventory.list_resource_groups(sub_id))
        return [
            g
            for g in groups
            if policy.resource_group(sub_id, g.name, environment) and policy.region_allowed(g.location)
        ]

    @app.get("/v1/subscriptions/{sub_id}/aks-clusters", response_model=list[AksClusterOut])
    def aks_clusters(_: Auth, sub_id: str, environment: str | None = None) -> list[AksClusterOut]:
        _allowed_sub(sub_id, environment)
        clusters = cache.get_or_load(f"aks:{sub_id}", lambda: inventory.list_aks_clusters(sub_id))
        out: list[AksClusterOut] = []
        for k in clusters:
            entry = policy.aks_cluster(sub_id, k.name, environment)
            if entry:
                out.append(
                    AksClusterOut(
                        **k.model_dump(),
                        zones=k.zones_spanned,
                        ha_eligible=k.zones_spanned >= policy.ha.min_zones,
                        base_domain=entry.gateway.base_domain if entry.gateway else None,
                    )
                )
        return out

    @app.get("/v1/subscriptions/{sub_id}/container-registries", response_model=list[ContainerRegistry])
    def registries(_: Auth, sub_id: str, environment: str | None = None) -> list[ContainerRegistry]:
        _allowed_sub(sub_id, environment)
        regs = cache.get_or_load(f"acr:{sub_id}", lambda: inventory.list_container_registries(sub_id))
        return [r for r in regs if policy.container_registry(sub_id, r.name, environment)]

    @app.get("/v1/subscriptions/{sub_id}/resources", response_model=list[DataResource])
    def data_resources(
        _: Auth,
        sub_id: str,
        type: Annotated[str, Query(pattern="^(storage|keyvault)$")],
        environment: str | None = None,
        resource_group: str | None = None,
    ) -> list[DataResource]:
        _allowed_sub(sub_id, environment)
        wanted = "microsoft.storage/storageaccounts" if type == "storage" else "microsoft.keyvault/vaults"
        items = cache.get_or_load(f"data:{sub_id}", lambda: inventory.list_data_resources(sub_id))
        return [
            d
            for d in items
            if d.type.lower() == wanted
            and (resource_group is None or d.resource_group.lower() == resource_group.lower())
            and (e := policy.data_resource(sub_id, d.name, environment)) is not None
            and e.type.lower() == wanted
        ]

    # ---------------- validation (always live, never cached) ----------------
    @app.post("/v1/validate", response_model=ValidationResult)
    def validate(_: Auth, body: ValidationRequest) -> ValidationResult:
        return validate_request(body, inventory, policy)

    return app


def run() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8001)  # noqa: S104 - container networking
