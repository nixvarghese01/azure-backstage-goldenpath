"""Read-only view of Azure. Implementations: ``SdkInventory`` (real) and ``MockInventory`` (local/tests)."""

from __future__ import annotations

from typing import Protocol

from azure_discovery.models import AksCluster, ContainerRegistry, DataResource, ResourceGroup, Subscription


class InventoryError(Exception):
    code = "unavailable"


class AzurePermissionError(InventoryError):
    code = "permission_denied"


class AzureThrottledError(InventoryError):
    code = "throttled"


class AzureUnavailableError(InventoryError):
    code = "unavailable"


class AzureInventory(Protocol):
    def list_subscriptions(self) -> list[Subscription]: ...

    def get_subscription(self, subscription_id: str) -> Subscription | None: ...

    def list_resource_groups(self, subscription_id: str) -> list[ResourceGroup]: ...

    def list_aks_clusters(self, subscription_id: str) -> list[AksCluster]: ...

    def list_container_registries(self, subscription_id: str) -> list[ContainerRegistry]: ...

    def list_data_resources(self, subscription_id: str) -> list[DataResource]: ...

    def regional_vcpus(self, subscription_id: str, region: str) -> tuple[int, int] | None:
        """Return (used, limit) for total regional vCPUs, or None if unknown."""
        ...

    def can_acquire_token(self) -> bool: ...
