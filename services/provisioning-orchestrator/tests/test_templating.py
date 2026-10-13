"""Generated descriptions must remain valid JSON and TypeScript string literals."""

import json
from pathlib import Path

import pytest

from provisioning_orchestrator.templating import render_stack


@pytest.mark.parametrize("description", [
    'Customer "orders" and backslash \\ paths',
    "Line one\nLine two\tTabbed\rReturn",
    "Customer's API: café </script>",
])
def test_description_is_serialized_in_generated_sources(description: str) -> None:
    templates = Path(__file__).resolve().parents[3] / "templates" / "applications"
    files = render_stack(templates, "nestjs/application", {
        "app": "orders-api", "description": description, "namespace": "orders-api",
        "endpoint_host": "orders-api.dev.sportify.example", "availability": {"tier": "standard"},
        "request_id": "00000000-0000-4000-8000-000000000001", "outputs": {}, "resolved": {},
        "runtime_capability": {"type": "storage", "mode": "existing"},
    })
    assert json.loads(files["package.json"])["description"] == description
    line = next(line.strip() for line in files["src/main.ts"].splitlines() if ".setDescription(" in line)
    assert json.loads(line.removeprefix(".setDescription(").removesuffix(")")) == description
