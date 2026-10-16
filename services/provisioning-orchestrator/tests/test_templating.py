"""Generated descriptions must remain valid JSON and TypeScript string literals."""

import json
from pathlib import Path

import pytest
from provisioning_orchestrator.templating import render_stack


@pytest.mark.parametrize("directory", ["bin", "obj", "tests/Checks/bin", "tests/Checks/obj"])
def test_renderer_skips_dotnet_build_output(tmp_path: Path, directory: str) -> None:
    application = tmp_path / "dotnet" / "application"
    artifact = application / directory / "cache.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"\xff\xfe\x00")
    (application / "Starter.csproj").write_text("<Project />", encoding="utf-8")

    assert render_stack(tmp_path, "dotnet/application", {}) == {"Starter.csproj": "<Project />"}


@pytest.mark.parametrize(
    "description",
    [
        'Customer "orders" and backslash \\ paths',
        "Line one\nLine two\tTabbed\rReturn",
        "Customer's API: café </script>",
    ],
)
def test_description_is_serialized_in_generated_sources(description: str) -> None:
    templates = Path(__file__).resolve().parents[3] / "templates" / "applications"
    files = render_stack(
        templates,
        "nestjs/application",
        {
            "app": "orders-api",
            "description": description,
            "namespace": "orders-api",
            "org": "nixvarghese01",
            "platform_ref": "develop",
            "repo": "orders-api",
            "owner": "group:default/team-orders",
            "environment": "dev",
            "endpoint_host": "orders-api.dev.xycorp.local",
            "availability": {"tier": "standard"},
            "request_id": "00000000-0000-4000-8000-000000000001",
            "outputs": {},
            "resolved": {},
            "runtime_capability": {"type": "storage", "mode": "existing"},
        },
    )
    assert json.loads(files["package.json"])["description"] == description
    line = next(line.strip() for line in files["src/main.ts"].splitlines() if ".setDescription(" in line)
    assert json.loads(line.removeprefix(".setDescription(").removesuffix(")")) == description
    assert 'org.opencontainers.image.title="orders-api"' in files["Dockerfile"]
    assert "image: orders-api:local" in files["docker-compose.yml"]
    assert 'AZURE_STORAGE_ACCOUNT: ""' in files["docker-compose.yml"]
    assert "git clone https://github.com/nixvarghese01/orders-api.git" in files["README.md"]
    assert "[[" not in "".join(files.values())
    # Generated workflows call the platform's reusable workflows at the platform ref (the deploying branch).
    ci = files[".github/workflows/application-ci.yml"]
    assert "reusable-application-ci.yml@develop" in ci
    assert "@main" not in ci
