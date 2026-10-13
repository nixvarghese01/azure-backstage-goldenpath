"""FastAPI application for azure-discovery (read-only)."""

# Route dependency aliases live inside create_app, so keep annotations evaluable in that scope.
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sportify_common.auth import Caller, require_caller
from sportify_common.logging import configure_logging
from sportify_common.telemetry import configure_tracing

from azure_discovery.cache import TtlCache
from azure_discovery.capabilities import compute_capabilities
from azure_discovery.config import Settings
from azure_discovery.inventory.base import AzureInventory, InventoryError
from azure_discovery.models import (
    AksClusterOut,
    Capabilities,
    ContainerRegistry,
    DataResource,
    ResourceGroup,
    Subscription,
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
        description="Read-only Azure discovery for Sportify Azure Backstage",
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

    # ---------------- discovery ----------------
    @app.get("/v1/subscriptions", response_model=list[Subscription])
    def subscriptions(_: Auth, environment: str | None = None) -> list[Subscription]:
        subs = cache.get_or_load("subs", inventory.list_subscriptions)
        out = []
        for s in subs:
            entry = policy.subscription(s.id)
            if (
                entry
                and s.state.lower() == "enabled"
                and (environment is None or environment in entry.environments)
            ):
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
    ) -> list[DataResource]:
        _allowed_sub(sub_id, environment)
        wanted = "microsoft.storage/storageaccounts" if type == "storage" else "microsoft.keyvault/vaults"
        items = cache.get_or_load(f"data:{sub_id}", lambda: inventory.list_data_resources(sub_id))
        return [
            d
            for d in items
            if d.type.lower() == wanted
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
