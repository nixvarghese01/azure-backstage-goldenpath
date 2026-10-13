"""Typed view of policies/allowlist.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EnvironmentPolicy(BaseModel):
    enabled: bool
    ha_default: bool
    approvers_required: int = 1


class SubscriptionEntry(BaseModel):
    id: str
    name: str
    environments: list[str]


class ScopedEntry(BaseModel):
    name: str
    subscription: str
    resource_group: str | None = None
    environments: list[str]


class GatewayRef(BaseModel):
    name: str
    namespace: str
    base_domain: str


class AksEntry(ScopedEntry):
    gateway: GatewayRef | None = None


class DataResourceEntry(ScopedEntry):
    type: str


class SubscriptionVending(BaseModel):
    billing_scope: str | None = None
    management_group: str | None = None


class CreateNew(BaseModel):
    subscription: bool = False
    resource_group: bool = False
    aks_cluster: bool = False
    container_registry: bool = False
    namespace: bool = False
    storage_account: bool = False
    key_vault: bool = False


class Skus(BaseModel):
    storage_account: list[str] = Field(default_factory=list)
    key_vault: list[str] = Field(default_factory=list)
    container_registry: list[str] = Field(default_factory=list)
    aks_node_vm: list[str] = Field(default_factory=list)


class Naming(BaseModel):
    application_pattern: str
    reserved_names: list[str] = Field(default_factory=list)


class StackEntry(BaseModel):
    id: str
    name: str
    enabled: bool
    runtime_capabilities: list[str] = Field(default_factory=lambda: ["storage", "keyvault", "none"])


class Justification(BaseModel):
    min_length: int = 30
    max_length: int = 500
    rejected_values: list[str] = Field(default_factory=list)


class HaPolicy(BaseModel):
    min_zones: int = 2
    slo_targets: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    justification: Justification = Field(default_factory=Justification)


class Roles(BaseModel):
    assignable: list[str] = Field(default_factory=list)


class Allowlist(BaseModel):
    version: int
    environments: dict[str, EnvironmentPolicy]
    regions: list[str]
    subscriptions: list[SubscriptionEntry]
    resource_groups: list[ScopedEntry] = Field(default_factory=list)
    aks_clusters: list[AksEntry] = Field(default_factory=list)
    container_registries: list[ScopedEntry] = Field(default_factory=list)
    data_resources: list[DataResourceEntry] = Field(default_factory=list)
    subscription_vending: SubscriptionVending = Field(default_factory=SubscriptionVending)
    create_new: CreateNew = Field(default_factory=CreateNew)
    skus: Skus = Field(default_factory=Skus)
    roles: Roles = Field(default_factory=Roles)
    naming: Naming
    stacks: list[StackEntry] = Field(default_factory=list)
    ha: HaPolicy = Field(default_factory=HaPolicy)

    # ---- lookups (case-insensitive, Azure names are case-insensitive) ----
    def subscription(self, sub_id: str) -> SubscriptionEntry | None:
        return next((s for s in self.subscriptions if s.id.lower() == sub_id.lower()), None)

    def region_allowed(self, region: str) -> bool:
        return region.lower() in {r.lower() for r in self.regions}

    @staticmethod
    def _match[E: ScopedEntry](entries: list[E], sub_id: str, name: str, env: str | None = None) -> E | None:
        for e in entries:
            if e.subscription.lower() == sub_id.lower() and e.name.lower() == name.lower():
                if env is None or env in e.environments:
                    return e
        return None

    def resource_group(self, sub_id: str, name: str, env: str | None = None) -> ScopedEntry | None:
        return self._match(self.resource_groups, sub_id, name, env)

    def aks_cluster(self, sub_id: str, name: str, env: str | None = None) -> AksEntry | None:
        return self._match(self.aks_clusters, sub_id, name, env)

    def container_registry(self, sub_id: str, name: str, env: str | None = None) -> ScopedEntry | None:
        return self._match(self.container_registries, sub_id, name, env)

    def data_resource(self, sub_id: str, name: str, env: str | None = None) -> DataResourceEntry | None:
        return self._match(self.data_resources, sub_id, name, env)


def load_allowlist(path: Path) -> Allowlist:
    with path.open(encoding="utf-8") as fh:
        return Allowlist.model_validate(yaml.safe_load(fh))
