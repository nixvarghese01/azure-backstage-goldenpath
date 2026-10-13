"""Every stack deploys as one right-sized pod, and local Compose uses the same resources."""

from pathlib import Path

import pytest
import yaml
from provisioning_orchestrator.templating import RUNTIME_PROFILES, render_stack, runtime_profile

TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "applications"
STACKS = sorted(p.name for p in TEMPLATES.iterdir() if (p / "application").is_dir())


def _render(stack: str) -> dict[str, str]:
    return render_stack(
        TEMPLATES,
        f"{stack}/application",
        {
            "app": "orders-api",
            "stack": stack,
            "description": "Orders",
            "namespace": "orders-api",
            "org": "nixvarghese01",
            "repo": "orders-api",
            "owner": "group:default/team-orders",
            "environment": "dev",
            "endpoint_host": "orders-api.dev.xycorp.local",
            "availability": {"tier": "standard"},
            "request_id": "00000000-0000-4000-8000-000000000001",
            "outputs": {},
            "resolved": {},
            "runtime_capability": {"type": "none", "mode": "existing"},
        },
    )


def test_every_stack_template_has_a_profile() -> None:
    assert set(STACKS) == set(RUNTIME_PROFILES)


@pytest.mark.parametrize("stack", STACKS)
def test_single_right_sized_pod_matches_compose(stack: str) -> None:
    profile = runtime_profile(stack)
    files = _render(stack)
    values = yaml.safe_load(files["deploy/helm/application/values-dev.yaml"])
    compose = yaml.safe_load(files["docker-compose.yml"])["services"]["application"]

    assert values["replicaCount"] == 1
    resources = values["resources"]
    assert resources["requests"]["memory"] == resources["limits"]["memory"] == f"{profile.memory_mi}Mi"
    assert resources["requests"]["cpu"] == f"{profile.cpu_request_m}m"
    assert resources["limits"]["cpu"] == f"{profile.cpu_limit_m}m"
    assert values["probes"]["startup"]["failureThreshold"] * 2 == profile.startup_seconds
    assert values.get("env", {}) == profile.env

    assert compose["mem_limit"] == f"${{APP_MEMORY:-{profile.memory_mi}m}}"
    assert compose["cpus"] == f"${{APP_CPUS:-{profile.cpu_limit_m / 1000:g}}}"
    for name, value in profile.env.items():
        assert compose["environment"][name] == value


def test_unknown_stack_is_rejected() -> None:
    with pytest.raises(ValueError, match="no runtime profile"):
        runtime_profile("cobol")
