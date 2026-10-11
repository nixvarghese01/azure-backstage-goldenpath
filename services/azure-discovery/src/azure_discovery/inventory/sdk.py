"""Real Azure inventory: Resource Graph + subscriptions + compute usage, read-only.

Authentication uses DefaultAzureCredential (Workload Identity on AKS, `az login` locally).
The Azure SDK pipeline already retries transient failures and honours Retry-After on 429; whatever
still fails is mapped to typed errors here - never to an empty success.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ServiceRequestError
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

from azure_discovery.inventory.base import (
    AzurePermissionError,
    AzureThrottledError,
    AzureUnavailableError,
)
from azure_discovery.models import (
    AksCluster,
    ContainerRegistry,
    DataResource,
    NodePool,
    ResourceGroup,
    Subscription,
)

log = logging.getLogger(__name__)

_ARM_SCOPE = "https://management.azure.com/.default"

_Q_RESOURCE_GROUPS = """
resourcecontainers
| where type == 'microsoft.resources/subscriptions/resourcegroups'
| project id, name, location
"""

_Q_AKS = """
resources
| where type == 'microsoft.containerservice/managedclusters'
| project id, name, resourceGroup, location,
          kubernetesVersion = tostring(properties.kubernetesVersion),
          oidc = tobool(properties.oidcIssuerProfile.enabled),
          wi = tobool(properties.securityProfile.workloadIdentity.enabled),
          pools = properties.agentPoolProfiles
"""

_Q_ACR = """
resources
| where type == 'microsoft.containerregistry/registries'
| project id, name, resourceGroup, location, sku = tostring(sku.name),
          loginServer = tostring(properties.loginServer)
"""

_Q_DATA = """
resources
| where type in ('microsoft.storage/storageaccounts', 'microsoft.keyvault/vaults')
| project id, name, type, resourceGroup, location, sku = tostring(sku.name)
"""


def _translate(exc: Exception) -> Exception:
    if isinstance(exc, ClientAuthenticationError):
        return AzurePermissionError("authentication failed for the discovery identity")
    if isinstance(exc, HttpResponseError):
        status = exc.status_code or 0
        if status in (401, 403):
            return AzurePermissionError("the discovery identity lacks Reader access")
        if status == 429:
            return AzureThrottledError("Azure throttled the request; retry later")
        return AzureUnavailableError(f"Azure returned HTTP {status}")
    if isinstance(exc, ServiceRequestError):
        return AzureUnavailableError("Azure is unreachable")
    return exc


class SdkInventory:
    def __init__(self) -> None:
        self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        self._graph = ResourceGraphClient(self._credential)
        self._subs = SubscriptionClient(self._credential)

    # ---- Resource Graph with skip-token paging ----
    def _query(self, subscription_id: str, kql: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        skip_token: str | None = None
        try:
            while True:
                options = QueryRequestOptions(result_format="objectArray", skip_token=skip_token, top=1000)
                result = self._graph.resources(
                    QueryRequest(subscriptions=[subscription_id], query=kql, options=options)
                )
                rows.extend(result.data or [])
                skip_token = result.skip_token
                if not skip_token:
                    return rows
        except Exception as exc:  # noqa: BLE001 - translated below
            raise _translate(exc) from exc

    def list_subscriptions(self) -> list[Subscription]:
        try:
            return [
                Subscription(
                    id=s.subscription_id,
                    name=s.display_name,
                    state=str(s.state),
                    quota_id=getattr(s.subscription_policies, "quota_id", None),
                )
                for s in self._subs.subscriptions.list()
            ]
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        try:
            s = self._subs.subscriptions.get(subscription_id)
        except HttpResponseError as exc:
            if exc.status_code == 404:
                return None
            raise _translate(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc
        return Subscription(
            id=s.subscription_id,
            name=s.display_name,
            state=str(s.state),
            quota_id=getattr(s.subscription_policies, "quota_id", None),
        )

    def list_resource_groups(self, subscription_id: str) -> list[ResourceGroup]:
        return [ResourceGroup(**r) for r in self._query(subscription_id, _Q_RESOURCE_GROUPS)]

    def list_aks_clusters(self, subscription_id: str) -> list[AksCluster]:
        clusters = []
        for r in self._query(subscription_id, _Q_AKS):
            pools = [
                NodePool(
                    name=p.get("name", ""),
                    mode=p.get("mode", "System"),
                    vm_size=p.get("vmSize", ""),
                    count=int(p.get("count") or 0),
                    zones=[str(z) for z in (p.get("availabilityZones") or [])],
                )
                for p in (r.get("pools") or [])
            ]
            clusters.append(
                AksCluster(
                    id=r["id"],
                    name=r["name"],
                    resource_group=r["resourceGroup"],
                    location=r["location"],
                    kubernetes_version=r.get("kubernetesVersion"),
                    oidc_issuer_enabled=bool(r.get("oidc")),
                    workload_identity_enabled=bool(r.get("wi")),
                    node_pools=pools,
                )
            )
        return clusters

    def list_container_registries(self, subscription_id: str) -> list[ContainerRegistry]:
        return [
            ContainerRegistry(
                id=r["id"], name=r["name"], resource_group=r["resourceGroup"], location=r["location"],
                sku=r.get("sku") or "", login_server=r.get("loginServer") or "",
            )
            for r in self._query(subscription_id, _Q_ACR)
        ]

    def list_data_resources(self, subscription_id: str) -> list[DataResource]:
        return [
            DataResource(
                id=r["id"], name=r["name"], type=r["type"], resource_group=r["resourceGroup"],
                location=r["location"], sku=r.get("sku"),
            )
            for r in self._query(subscription_id, _Q_DATA)
        ]

    def regional_vcpus(self, subscription_id: str, region: str) -> tuple[int, int] | None:
        try:
            client = ComputeManagementClient(self._credential, subscription_id)
            for usage in client.usage.list(region):
                if usage.name and usage.name.value == "cores":
                    return int(usage.current_value), int(usage.limit)
        except Exception as exc:  # noqa: BLE001 - quota is advisory
            log.warning("could not read vCPU usage: %s", type(exc).__name__)
        return None

    def can_acquire_token(self) -> bool:
        try:
            self._credential.get_token(_ARM_SCOPE)
            return True
        except Exception:  # noqa: BLE001
            return False
