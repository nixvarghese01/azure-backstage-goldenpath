"""Which "Create new" options a subscription can support, with human-readable reasons."""

from __future__ import annotations

from azure_discovery.inventory.base import AzureInventory
from azure_discovery.models import Capabilities, CapabilityOption
from azure_discovery.policy import Allowlist

# Minimal footprint for a new shared cluster: one system node with 2 vCPUs.
NEW_AKS_MIN_VCPUS = 2


def compute_capabilities(
    subscription_id: str, region: str, inventory: AzureInventory, policy: Allowlist
) -> Capabilities:
    sub = inventory.get_subscription(subscription_id)
    quota_id = sub.quota_id if sub else None
    cn = policy.create_new
    options: dict[str, CapabilityOption] = {}

    # Subscription vending needs an EA/MCA billing scope configured by the platform team.
    if not cn.subscription:
        options["subscription"] = CapabilityOption(available=False, reason="Disabled by platform policy.")
    elif not policy.subscription_vending.billing_scope:
        options["subscription"] = CapabilityOption(
            available=False,
            reason="Subscription vending needs an EA or MCA billing account "
            "(free and pay-as-you-go accounts can't create subscriptions).",
        )
    else:
        options["subscription"] = CapabilityOption(available=True)

    vcpus = inventory.regional_vcpus(subscription_id, region)
    if not cn.aks_cluster:
        options["aks_cluster"] = CapabilityOption(available=False, reason="Disabled by platform policy.")
    elif vcpus is None:
        options["aks_cluster"] = CapabilityOption(
            available=True, reason="vCPU quota couldn't be read; it will be checked at plan time."
        )
    else:
        used, limit = vcpus
        free = limit - used
        options["aks_cluster"] = (
            CapabilityOption(available=True)
            if free >= NEW_AKS_MIN_VCPUS
            else CapabilityOption(
                available=False,
                reason=f"Regional vCPU quota too low: {free} free of {limit} in {region}, "
                f"a new cluster needs at least {NEW_AKS_MIN_VCPUS}.",
            )
        )

    for key in ("resource_group", "container_registry", "namespace", "storage_account", "key_vault"):
        enabled = getattr(cn, key)
        options[key] = CapabilityOption(
            available=enabled, reason=None if enabled else "Disabled by platform policy."
        )

    return Capabilities(
        subscription_id=subscription_id,
        quota_id=quota_id,
        create_new=options,
        regional_vcpus={"used": vcpus[0], "limit": vcpus[1]} if vcpus else None,
    )
