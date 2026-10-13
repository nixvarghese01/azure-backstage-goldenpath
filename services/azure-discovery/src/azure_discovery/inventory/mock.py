"""In-memory Azure inventory for local development and tests. Matches the example allowlist."""

from __future__ import annotations

from azure_discovery.models import (
    AksCluster,
    ContainerRegistry,
    DataResource,
    NodePool,
    ResourceGroup,
    Subscription,
)

SUB = "00000000-0000-0000-0000-000000000000"
_P = f"/subscriptions/{SUB}/resourceGroups"


class MockInventory:
    def __init__(
        self,
        *,
        vcpus: tuple[int, int] | None = (2, 4),
        cluster_zones: list[str] | None = None,
        extra_subscriptions: list[Subscription] | None = None,
    ) -> None:
        self.subscriptions = [
            Subscription(id=SUB, name="sub-sportify-dev", state="Enabled", quota_id="FreeTrial_2014-09-01"),
            Subscription(id="11111111-1111-1111-1111-111111111111", name="not-allowlisted", state="Enabled"),
            *(extra_subscriptions or []),
        ]
        self.resource_groups = [
            ResourceGroup(id=f"{_P}/rg-sportify-apps-dev", name="rg-sportify-apps-dev", location="uksouth"),
            ResourceGroup(
                id=f"{_P}/rg-sportify-platform-dev", name="rg-sportify-platform-dev", location="uksouth"
            ),
            ResourceGroup(id=f"{_P}/rg-other", name="rg-other", location="westeurope"),
        ]
        self.clusters = [
            AksCluster(
                id=f"{_P}/rg-sportify-platform-dev/providers/Microsoft.ContainerService/managedClusters/"
                "aks-sportify-shared-dev",
                name="aks-sportify-shared-dev",
                resource_group="rg-sportify-platform-dev",
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
                id=f"{_P}/rg-sportify-platform-dev/providers/Microsoft.ContainerRegistry/registries/"
                "acrsportifydev",
                name="acrsportifydev",
                resource_group="rg-sportify-platform-dev",
                location="uksouth",
                sku="Basic",
                login_server="acrsportifydev.azurecr.io",
            )
        ]
        self.data = [
            DataResource(
                id=f"{_P}/rg-sportify-apps-dev/providers/Microsoft.Storage/storageAccounts/stsportifyshareddev",
                name="stsportifyshareddev",
                type="microsoft.storage/storageaccounts",
                resource_group="rg-sportify-apps-dev",
                location="uksouth",
                sku="Standard_LRS",
            )
        ]
        self.vcpus = vcpus

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
