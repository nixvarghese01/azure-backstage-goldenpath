"""In-memory Azure inventory for local development and tests. Matches the example allowlist.

The tenant follows the Cloud Adoption Framework (Azure landing zones) management group hierarchy:

    Tenant Root Group
    └── XY Corp (intermediate root)
        ├── Platform: Management, Connectivity, Identity
        ├── Landing zones: Corp (sub-idp-dev), Online
        ├── Sandbox (not-allowlisted)
        └── Decommissioned
"""

from __future__ import annotations

from azure_discovery.models import (
    AksCluster,
    ContainerRegistry,
    DataResource,
    ManagementGroup,
    NodePool,
    ResourceGroup,
    Subscription,
    Tenant,
)

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SUB = "00000000-0000-0000-0000-000000000000"
_P = f"/subscriptions/{SUB}/resourceGroups"

# (id, display name, parent id): the Azure landing zones reference hierarchy.
_CAF = [
    (TENANT, "Tenant Root Group", None),
    ("xycorp", "XY Corp", TENANT),
    ("xycorp-platform", "Platform", "xycorp"),
    ("xycorp-management", "Management", "xycorp-platform"),
    ("xycorp-connectivity", "Connectivity", "xycorp-platform"),
    ("xycorp-identity", "Identity", "xycorp-platform"),
    ("xycorp-landingzones", "Landing zones", "xycorp"),
    ("xycorp-corp", "Corp", "xycorp-landingzones"),
    ("xycorp-online", "Online", "xycorp-landingzones"),
    ("xycorp-sandbox", "Sandbox", "xycorp"),
    ("xycorp-decommissioned", "Decommissioned", "xycorp"),
]
_PARENT = {mg: parent for mg, _, parent in _CAF}


def _chain(mg: str) -> list[str]:
    """Management group ids from ``mg`` up to the Tenant Root Group."""
    out: list[str] = []
    cur: str | None = mg
    while cur:
        out.append(cur)
        cur = _PARENT[cur]
    return out


class MockInventory:
    def __init__(
        self,
        *,
        vcpus: tuple[int, int] | None = (2, 4),
        cluster_zones: list[str] | None = None,
        extra_subscriptions: list[Subscription] | None = None,
    ) -> None:
        self.tenants = [Tenant(id=TENANT, name="XY Corp", default_domain="xycorp.onmicrosoft.com")]
        self.management_groups = [
            ManagementGroup(id=mg, name=name, tenant_id=TENANT, parent_id=parent) for mg, name, parent in _CAF
        ]
        self.subscriptions = [
            Subscription(
                id=SUB,
                name="sub-idp-dev",
                state="Enabled",
                quota_id="FreeTrial_2014-09-01",
                tenant_id=TENANT,
                management_groups=_chain("xycorp-corp"),
            ),
            Subscription(
                id="11111111-1111-1111-1111-111111111111",
                name="not-allowlisted",
                state="Enabled",
                tenant_id=TENANT,
                management_groups=_chain("xycorp-sandbox"),
            ),
            *(extra_subscriptions or []),
        ]
        self.resource_groups = [
            ResourceGroup(id=f"{_P}/rg-idp-apps-dev", name="rg-idp-apps-dev", location="uksouth"),
            ResourceGroup(id=f"{_P}/rg-idp-aks-dev", name="rg-idp-aks-dev", location="uksouth"),
            ResourceGroup(id=f"{_P}/rg-idp-registry-dev", name="rg-idp-registry-dev", location="uksouth"),
            ResourceGroup(id=f"{_P}/rg-other", name="rg-other", location="westeurope"),
        ]
        self.clusters = [
            AksCluster(
                id=f"{_P}/rg-idp-aks-dev/providers/Microsoft.ContainerService/managedClusters/"
                "aks-idp-shared-dev",
                name="aks-idp-shared-dev",
                resource_group="rg-idp-aks-dev",
                location="uksouth",
                kubernetes_version="1.36.4",
                oidc_issuer_enabled=True,
                workload_identity_enabled=True,
                node_pools=[
                    NodePool(
                        name="system",
                        mode="System",
                        vm_size="Standard_D2s_v5",
                        count=1,
                        zones=cluster_zones or [],
                    )
                ],
            )
        ]
        self.registries = [
            ContainerRegistry(
                id=f"{_P}/rg-idp-registry-dev/providers/Microsoft.ContainerRegistry/registries/acridpdev",
                name="acridpdev",
                resource_group="rg-idp-registry-dev",
                location="uksouth",
                sku="Basic",
                login_server="acridpdev.azurecr.io",
            )
        ]
        self.data = [
            DataResource(
                id=f"{_P}/rg-idp-apps-dev/providers/Microsoft.Storage/storageAccounts/stidpshareddev",
                name="stidpshareddev",
                type="microsoft.storage/storageaccounts",
                resource_group="rg-idp-apps-dev",
                location="uksouth",
                sku="Standard_LRS",
            )
        ]
        self.vcpus = vcpus

    def list_tenants(self) -> list[Tenant]:
        return list(self.tenants)

    def list_management_groups(self) -> list[ManagementGroup]:
        return list(self.management_groups)

    def list_subscriptions(self) -> list[Subscription]:
        return list(self.subscriptions)

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        return next((s for s in self.subscriptions if s.id.lower() == subscription_id.lower()), None)

    def _in(self, subscription_id: str) -> bool:
        return subscription_id.lower() == SUB

    def list_resource_groups(self, subscription_id: str) -> list[ResourceGroup]:
        return list(self.resource_groups) if self._in(subscription_id) else []

    def list_aks_clusters(self, subscription_id: str) -> list[AksCluster]:
        return list(self.clusters) if self._in(subscription_id) else []

    def list_container_registries(self, subscription_id: str) -> list[ContainerRegistry]:
        return list(self.registries) if self._in(subscription_id) else []

    def list_data_resources(self, subscription_id: str) -> list[DataResource]:
        return list(self.data) if self._in(subscription_id) else []

    def regional_vcpus(self, subscription_id: str, region: str) -> tuple[int, int] | None:
        return self.vcpus

    def can_acquire_token(self) -> bool:
        return True
