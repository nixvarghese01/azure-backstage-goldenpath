"""Render the shared infrastructure skeleton plus a selected application stack for ci-templates.yml.

The skeleton uses Backstage's ``${{ values.x }}`` syntax; this script substitutes the few expressions the
skeleton uses so the result is a realistic generated repository. The application stack is rendered
with the orchestrator's own renderer, exactly as in production.
Usage: python render_fixture.py <output-dir> [--stack nestjs|fastapi|go|dotnet|springboot|nextjs|react|vue]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from provisioning_orchestrator.templating import render_stack

HERE = Path(__file__).resolve().parent
FIXTURE = {
    "name": "orders-api",
    "description": "Order management REST API",
    "owner": "group:default/team-orders",
    "environment": "dev",
    "requestId": "00000000-0000-4000-8000-000000000001",
    "org": "nixvarghese01",
    "availabilityTier": "standard",
    "endpointHost": "orders-api.dev.xycorp.local",
    "infrastructure.region": "uksouth",
    "infrastructure.subscription.id": "00000000-0000-0000-0000-000000000000",
    "infrastructure.resourceGroup.mode": "existing",
    "infrastructure.resourceGroup.name": "rg-idp-apps-dev",
    "infrastructure.aksCluster.name": "aks-idp-shared-dev",
    "infrastructure.aksCluster.resourceGroup": "rg-idp-aks-dev",
    "infrastructure.containerRegistry.name": "acridpdev",
    "infrastructure.containerRegistry.resourceGroup": "rg-idp-registry-dev",
    "infrastructure.namespace.mode": "new",
    "infrastructure.namespace.name": "orders-api",
    "infrastructure.runtimeCapability.type": "storage",
    "infrastructure.runtimeCapability.mode": "existing",
    "infrastructure.runtimeCapability.name": "stidpshareddev",
    "infrastructure.runtimeCapability.resourceGroup": "rg-idp-apps-dev",
}
EXPR = re.compile(r"\$\{\{\s*values\.([a-zA-Z0-9_.]+)\s*(\|[^}]*)?\}\}")
COPY_ONLY = (".github/workflows/", "deploy/helm/", "infra/terraform/main.tf", "infra/terraform/versions.tf",
             "infra/terraform/providers.tf", "infra/terraform/variables.tf", "infra/terraform/outputs.tf")


def render_skeleton(out: Path) -> None:
    src = HERE / "skeleton"
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel.startswith(COPY_ONLY):
            shutil.copyfile(path, target)
            continue

        def sub(m: re.Match[str]) -> str:
            value = FIXTURE[m.group(1)]
            filt = (m.group(2) or "").strip()
            if "replace('group:default/', '')" in filt:
                value = value.replace("group:default/", "")
            if filt == "| dump":
                return json.dumps(value)
            return value

        target.write_text(EXPR.sub(sub, path.read_text(encoding="utf-8")), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--stack",
        choices=["nestjs", "fastapi", "go", "dotnet", "springboot", "nextjs", "react", "vue"],
        default="nestjs",
    )
    args = parser.parse_args()
    FIXTURE["stack"] = args.stack
    out = args.output
    if args.stack != "nestjs":
        FIXTURE["infrastructure.runtimeCapability.type"] = "none"
        FIXTURE["infrastructure.runtimeCapability.name"] = ""
        FIXTURE["infrastructure.runtimeCapability.resourceGroup"] = ""
    if out.exists():
        shutil.rmtree(out)
    render_skeleton(out)
    values = {
        "app": "orders-api", "description": "Order management REST API", "owner": "group:default/team-orders",
        "stack": args.stack,
        "environment": "dev", "request_id": FIXTURE["requestId"], "org": "nixvarghese01", "platform_ref": "main", "repo": "orders-api",
        "namespace": "orders-api", "endpoint_host": FIXTURE["endpointHost"],
        "availability": {"tier": "standard"}, "runtime_capability": {"type": "storage", "mode": "existing"},
        "outputs": {"identity_client_id": "11111111-1111-1111-1111-111111111111",
                    "acr_login_server": "acridpdev.azurecr.io", "storage_account_name": "stidpshareddev"},
        "resolved": {},
    }
    if args.stack != "nestjs":
        values["runtime_capability"] = {"type": "none", "mode": "existing"}
        values["outputs"].pop("storage_account_name", None)
    for rel, content in render_stack(HERE.parent, f"{args.stack}/application", values).items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"rendered fixture repository into {out}")


if __name__ == "__main__":
    main()
