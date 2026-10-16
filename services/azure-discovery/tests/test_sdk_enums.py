from enum import Enum

from azure_discovery.inventory.sdk import _enum_text


# The Azure SDK's enum shape (str mixin); StrEnum would print its value and hide the bug.
class SubscriptionState(str, Enum):  # noqa: UP042
    ENABLED = "Enabled"


def test_enum_text_uses_the_wire_value():
    # str() would give "SubscriptionState.ENABLED" (Python 3.11+); the API layer compares with "enabled".
    assert str(SubscriptionState.ENABLED) != "Enabled"
    assert _enum_text(SubscriptionState.ENABLED) == "Enabled"


def test_enum_text_plain_values():
    assert _enum_text("Disabled") == "Disabled"
    assert _enum_text(None) == ""
