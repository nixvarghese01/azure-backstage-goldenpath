"""Opt-in tests against real Azure (read-only). Run with:
    RUN_LIVE_AZURE_TESTS=1 LIVE_SUBSCRIPTION_ID=<id> az login && uv run pytest -m live_azure
They never create or change anything: the discovery identity is Reader-only by design."""

import os

import pytest

pytestmark = [
    pytest.mark.live_azure,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_AZURE_TESTS") != "1", reason="set RUN_LIVE_AZURE_TESTS=1"),
]


@pytest.fixture(scope="module")
def sdk():
    from azure_discovery.inventory.sdk import SdkInventory

    return SdkInventory()


def test_credential_works(sdk) -> None:
    assert sdk.can_acquire_token()


def test_lists_subscriptions_and_resource_groups(sdk) -> None:
    sub = os.environ["LIVE_SUBSCRIPTION_ID"]
    subs = {s.id for s in sdk.list_subscriptions()}
    assert sub in subs
    groups = sdk.list_resource_groups(sub)
    assert all(g.id.lower().startswith(f"/subscriptions/{sub}".lower()) for g in groups)


def test_aks_and_quota_are_readable(sdk) -> None:
    sub = os.environ["LIVE_SUBSCRIPTION_ID"]
    for cluster in sdk.list_aks_clusters(sub):
        assert cluster.name
    region = os.environ.get("LIVE_REGION", "uksouth")
    usage = sdk.regional_vcpus(sub, region)
    assert usage is None or usage[1] >= usage[0] >= 0
