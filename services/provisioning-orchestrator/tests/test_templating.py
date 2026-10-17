"""Generated descriptions must remain valid JSON and TypeScript string literals."""

import json
from pathlib import Path

import pytest
from provisioning_orchestrator.templating import render_stack, render_starter


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


def test_starter_leaves_out_what_needs_the_infrastructure(tmp_path: Path) -> None:
    root = tmp_path / "nestjs"
    for rel, text in {
        "src/main.ts.j2": "// [[ values.app ]]\n",
        "Dockerfile": "FROM node:24-alpine\n",
        ".github/workflows/application-ci.yml.j2": "name: ci\n",
        "deploy/helm/application/values-dev.yaml.j2": "kv: [[ values.outputs.get('key_vault_uri', '') ]]\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")

    assert render_starter(tmp_path, "nestjs", {"app": "orders-api"}) == {
        "Dockerfile": "FROM node:24-alpine\n",
        "src/main.ts": "// orders-api\n",
    }


def test_nestjs_starter_has_source_tests_and_dockerfile() -> None:
    templates = Path(__file__).resolve().parents[3] / "templates" / "applications"
    files = render_starter(
        templates,
        "nestjs/application",
        {
            "app": "orders-api",
            "stack": "nestjs",
            "description": "Orders",
            "owner": "group:default/platform-team",
            "environment": "dev",
            "request_id": "r-1",
            "namespace": "orders-api",
            "org": "nixvarghese01",
            "platform_ref": "develop",
            "repo": "orders-api",
            "endpoint_host": "",
            "availability": {"tier": "standard"},
        },
    )
    for path in ("Dockerfile", "package.json", "src/main.ts", "src/app.module.ts", "test/app.e2e-spec.ts"):
        assert path in files
    assert not [p for p in files if p.startswith((".github/", "deploy/"))]
