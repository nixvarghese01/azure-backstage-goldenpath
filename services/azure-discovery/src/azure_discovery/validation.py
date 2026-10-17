"""Server-side eligibility validation for a complete selection set (POST /v1/validate).

Never trusts IDs from the browser: every "existing" selection is re-resolved against live Azure data
and the allowlist; every "new" name is checked against naming rules, region and SKU allowlists, and the
subscription's capabilities. HA choices are checked against ADR-0004.
"""

from __future__ import annotations

import re

from azure_discovery.capabilities import compute_capabilities
from azure_discovery.inventory.base import AzureInventory
from azure_discovery.models import AksCluster, Finding, ValidationRequest, ValidationResult
from azure_discovery.policy import Allowlist

RG_NAME = re.compile(r"^rg-[a-z0-9-]{2,80}$")
NAMESPACE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
STORAGE_NAME = re.compile(r"^[a-z0-9]{3,24}$")
KEYVAULT_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$")
ACR_NAME = re.compile(r"^[a-zA-Z0-9]{5,50}$")
AKS_NAME = re.compile(r"^[a-z][a-z0-9-]{1,61}[a-z0-9]$")


def _under(management_group: str, tenant_id: str | None, ancestors: list[str]) -> bool:
    """True when a subscription with these ancestors sits below ``management_group``.

    The Tenant Root Group's id is the tenant id, so every subscription in the tenant is below it.
    """
    mg = management_group.lower()
    return mg == (tenant_id or "").lower() or mg in {a.lower() for a in ancestors}


def _name_from_id(resource_id: str | None) -> str | None:
    return resource_id.rstrip("/").split("/")[-1] if resource_id else None


class _Collector:
    def __init__(self) -> None:
        self.errors: list[Finding] = []
        self.warnings: list[Finding] = []

    def error(self, field: str, code: str, message: str) -> None:
        self.errors.append(Finding(field=field, code=code, message=message))

    def warn(self, field: str, code: str, message: str) -> None:
        self.warnings.append(Finding(field=field, code=code, message=message))


def validate_request(
    req: ValidationRequest, inventory: AzureInventory, policy: Allowlist
) -> ValidationResult:
    c = _Collector()
    resolved: dict[str, str] = {}
    platform_changes: list[str] = []
    env = req.environment

    # ---- environment, region, application, stack ----
    env_policy = policy.environments.get(env)
    if not env_policy or not env_policy.enabled:
        c.error("environment", "environment_not_enabled", f"Environment '{env}' is not enabled.")
    if not policy.region_allowed(req.region):
        c.error("region", "region_not_allowed", f"Region '{req.region}' is not on the allowlist.")
    if not re.fullmatch(policy.naming.application_pattern, req.application_name):
        c.error(
            "application_name",
            "invalid_name",
            "Use 4-32 lowercase letters, digits and hyphens, starting with a letter.",
        )
    if req.application_name in policy.naming.reserved_names:
        c.error("application_name", "reserved_name", f"'{req.application_name}' is reserved.")
    stack = next((s for s in policy.stacks if s.id == req.stack), None)
    if not stack or not stack.enabled:
        c.error("stack", "stack_not_available", f"Stack '{req.stack}' is not available yet.")
    if stack and req.runtime_capability.type not in stack.runtime_capabilities:
        c.error(
            "runtime_capability",
            "stack_capability_not_supported",
            f"Stack '{req.stack}' supports runtime capabilities: {', '.join(stack.runtime_capabilities)}.",
        )

    # ---- subscription ----
    sub_id = req.subscription.id or ""
    caps = None
    if req.subscription.mode == "new":
        platform_changes.append("subscription")
        if not policy.create_new.subscription or not policy.subscription_vending.billing_scope:
            c.error(
                "subscription",
                "capability_unavailable",
                "Subscription vending needs an EA or MCA billing account.",
            )
        # A vended subscription has no resources yet: everything below must be "new".
        for field in ("resource_group", "aks_cluster", "container_registry"):
            if getattr(req, field).mode != "new":
                c.error(field, "requires_new", f"A new subscription needs a new {field.replace('_', ' ')}.")
    else:
        entry = policy.subscription(sub_id)
        live = inventory.get_subscription(sub_id) if sub_id else None
        if not entry or env not in entry.environments:
            c.error("subscription", "not_allowlisted", "Subscription is not approved for this environment.")
        elif not live or live.state.lower() != "enabled":
            c.error("subscription", "not_found", "Subscription not found or not enabled.")
        elif not policy.tenant_allowed(live.tenant_id) or (
            req.tenant_id and (live.tenant_id or "").lower() != req.tenant_id.lower()
        ):
            c.error("tenant_id", "wrong_tenant", "The subscription isn't in the selected, approved tenant.")
        elif not policy.in_application_scope(live.management_groups):
            c.error(
                "management_group",
                "outside_landing_zone",
                "The subscription isn't under a management group approved for applications.",
            )
        elif req.management_group and not _under(
            req.management_group, live.tenant_id, live.management_groups
        ):
            c.error(
                "management_group",
                "not_in_management_group",
                f"The subscription isn't under management group '{req.management_group}'.",
            )
        else:
            resolved["subscription_id"] = live.id
            caps = compute_capabilities(sub_id, req.region, inventory, policy)

    existing_sub_ok = req.subscription.mode == "existing" and "subscription_id" in resolved

    # ---- resource group ----
    rg = req.resource_group
    if rg.mode == "new":
        if not policy.create_new.resource_group:
            c.error("resource_group", "capability_unavailable", "Creating resource groups is disabled.")
        if not rg.name or not RG_NAME.fullmatch(rg.name):
            c.error("resource_group", "invalid_name", "Resource group names must look like 'rg-<name>'.")
        elif existing_sub_ok and any(
            g.name.lower() == rg.name.lower() for g in inventory.list_resource_groups(sub_id)
        ):
            c.error("resource_group", "already_exists", f"Resource group '{rg.name}' already exists.")
    elif existing_sub_ok:
        name = rg.name or _name_from_id(rg.id) or ""
        if not policy.resource_group(sub_id, name, env):
            c.error("resource_group", "not_allowlisted", f"Resource group '{name}' is not approved.")
        else:
            live_rg = next(
                (g for g in inventory.list_resource_groups(sub_id) if g.name.lower() == name.lower()), None
            )
            if not live_rg:
                c.error("resource_group", "not_found", f"Resource group '{name}' was not found.")
            elif not policy.region_allowed(live_rg.location):
                c.error(
                    "resource_group", "region_not_allowed", f"'{name}' is in a region that isn't allowed."
                )
            else:
                resolved["resource_group_id"] = live_rg.id

    # ---- AKS cluster ----
    cluster: AksCluster | None = None
    aks = req.aks_cluster
    if aks.mode == "new":
        platform_changes.append("aks_cluster")
        if not aks.name or not AKS_NAME.fullmatch(aks.name):
            c.error("aks_cluster", "invalid_name", "Invalid AKS cluster name.")
        if caps and not caps.create_new["aks_cluster"].available:
            c.error("aks_cluster", "capability_unavailable", caps.create_new["aks_cluster"].reason or "")
    elif existing_sub_ok:
        name = aks.name or _name_from_id(aks.id) or ""
        aks_entry = policy.aks_cluster(sub_id, name, env)
        if not aks_entry:
            c.error("aks_cluster", "not_allowlisted", f"Cluster '{name}' is not an approved shared cluster.")
        else:
            cluster = next(
                (k for k in inventory.list_aks_clusters(sub_id) if k.name.lower() == name.lower()), None
            )
            if not cluster:
                c.error("aks_cluster", "not_found", f"Cluster '{name}' was not found.")
            elif not (cluster.oidc_issuer_enabled and cluster.workload_identity_enabled):
                c.error(
                    "aks_cluster",
                    "workload_identity_disabled",
                    "The cluster needs the OIDC issuer and Workload Identity enabled.",
                )
            else:
                resolved["aks_cluster_id"] = cluster.id
            if aks_entry.gateway:
                _resolve_endpoint_host(req, aks_entry.gateway.base_domain, resolved, c)

    # ---- container registry ----
    acr = req.container_registry
    if acr.mode == "new":
        platform_changes.append("container_registry")
        if not acr.name or not ACR_NAME.fullmatch(acr.name):
            c.error("container_registry", "invalid_name", "Registry names are 5-50 letters or digits.")
        c.warn("container_registry", "global_name", "Registry name availability is checked at plan time.")
    elif existing_sub_ok:
        name = acr.name or _name_from_id(acr.id) or ""
        if not policy.container_registry(sub_id, name, env):
            c.error("container_registry", "not_allowlisted", f"Registry '{name}' is not approved.")
        else:
            reg = next(
                (r for r in inventory.list_container_registries(sub_id) if r.name.lower() == name.lower()),
                None,
            )
            if not reg:
                c.error("container_registry", "not_found", f"Registry '{name}' was not found.")
            else:
                resolved["container_registry_id"] = reg.id
                resolved["container_registry_login_server"] = reg.login_server

    # ---- namespace (cluster-side; existence is confirmed at plan time) ----
    ns = req.namespace
    ns_name = ns.name or ""
    if (
        not NAMESPACE.fullmatch(ns_name)
        or ns_name.startswith("kube-")
        or ns_name in policy.naming.reserved_names
    ):
        c.error("namespace", "invalid_name", "Namespace must be a DNS label and not a reserved name.")
    if ns.mode == "existing":
        c.warn("namespace", "checked_at_plan", "Existing namespace ownership is checked at plan time.")

    # ---- runtime capability (Storage / Key Vault) ----
    rc = req.runtime_capability
    ha = req.availability.tier == "ha"
    if rc.type != "none":
        res_type = (
            "microsoft.storage/storageaccounts" if rc.type == "storage" else "microsoft.keyvault/vaults"
        )
        if rc.mode == "new":
            pattern = STORAGE_NAME if rc.type == "storage" else KEYVAULT_NAME
            allowed = (
                policy.create_new.storage_account if rc.type == "storage" else policy.create_new.key_vault
            )
            if not allowed:
                c.error("runtime_capability", "capability_unavailable", f"Creating {rc.type} is disabled.")
            if not rc.name or not pattern.fullmatch(rc.name):
                c.error("runtime_capability", "invalid_name", f"Invalid {rc.type} name.")
            if rc.type == "storage" and ha and "Standard_ZRS" not in policy.skus.storage_account:
                c.error("runtime_capability", "sku_not_allowed", "Zone-redundant storage isn't allowlisted.")
        elif existing_sub_ok:
            name = rc.name or _name_from_id(rc.id) or ""
            data_entry = policy.data_resource(sub_id, name, env)
            if not data_entry or data_entry.type.lower() != res_type:
                c.error("runtime_capability", "not_allowlisted", f"'{name}' is not approved for reuse.")
            else:
                live_data = next(
                    (
                        d
                        for d in inventory.list_data_resources(sub_id)
                        if d.name.lower() == name.lower() and d.type.lower() == res_type
                    ),
                    None,
                )
                if not live_data:
                    c.error("runtime_capability", "not_found", f"'{name}' was not found.")
                else:
                    resolved["runtime_resource_id"] = live_data.id
                    if ha and rc.type == "storage" and (live_data.sku or "").upper().endswith("_LRS"):
                        c.warn(
                            "runtime_capability",
                            "ha_with_lrs",
                            "HA was requested but the existing storage account is locally redundant (LRS).",
                        )

    # ---- availability (ADR-0004) ----
    _validate_availability(req, policy, cluster, c)

    return ValidationResult(
        valid=not c.errors,
        errors=c.errors,
        warnings=c.warnings,
        platform_changes=platform_changes,
        resolved=resolved,
    )


HOSTNAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)+$")


def _resolve_endpoint_host(
    req: ValidationRequest, base_domain: str, resolved: dict[str, str], c: _Collector
) -> None:
    """Default the endpoint host to <app>.<base_domain>; a custom host must be a valid DNS name."""
    host = (req.endpoint_host or f"{req.application_name}.{base_domain}").lower()
    if not HOSTNAME.fullmatch(host) or len(host) > 253:
        c.error("endpoint_host", "invalid_host", f"'{host}' is not a valid host name.")
        return
    if not host.endswith(f".{base_domain}"):
        c.warn(
            "endpoint_host",
            "outside_gateway_domain",
            f"'{host}' is outside the gateway domain {base_domain}; "
            "add its DNS record and certificate yourself.",
        )
    resolved["endpoint_host"] = host


def _validate_availability(
    req: ValidationRequest, policy: Allowlist, cluster: AksCluster | None, c: _Collector
) -> None:
    av = req.availability
    env_policy = policy.environments.get(req.environment)
    default_ha = bool(env_policy and env_policy.ha_default)
    wants_ha = av.tier == "ha"

    if wants_ha != default_ha:
        if not av.reason or av.reason not in policy.ha.reasons:
            c.error(
                "availability.reason",
                "reason_required",
                "Choose a reason when deviating from the environment's default availability.",
            )
        text = (av.justification or "").strip()
        rules = policy.ha.justification
        if text.lower() in {v.lower() for v in rules.rejected_values} or len(text) < rules.min_length:
            c.error(
                "availability.justification",
                "justification_required",
                f"Explain why in at least {rules.min_length} characters.",
            )
        elif len(text) > rules.max_length:
            c.error(
                "availability.justification",
                "justification_too_long",
                f"Keep the justification under {rules.max_length} characters.",
            )

    if wants_ha:
        if av.slo_target and av.slo_target not in policy.ha.slo_targets:
            c.error("availability.slo_target", "invalid_slo", "Choose one of the offered SLO targets.")
        if cluster is not None and cluster.zones_spanned < policy.ha.min_zones:
            c.error(
                "availability",
                "cluster_not_zonal",
                f"HA needs a node pool spanning at least {policy.ha.min_zones} availability zones; "
                f"'{cluster.name}' spans {cluster.zones_spanned}.",
            )
