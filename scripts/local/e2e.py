"""End-to-end check of the running local platform through its real interfaces (make e2e).

Runs in a throwaway python container on the Compose network, standard library only:
Backstage health, discovery's approved resources (including the gateway domain), then a golden-path
request through the orchestrator API that must validate with the derived endpoint host. The request
is cancelled afterwards, so nothing is left behind.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

TOKEN = os.environ.get("IDP_DEV_SERVICE_TOKEN", "dev-only-change-me")
BACKSTAGE = "http://backstage:7007"
DISCOVERY = "http://azure-discovery:8001"
ORCHESTRATOR = "http://orchestrator-api:8002"
SUB = "00000000-0000-0000-0000-000000000000"
SERVICE = {"Authorization": f"Bearer {TOKEN}"}
REQUESTER = {**SERVICE, "X-IDP-User": "user:default/e2e", "X-IDP-Groups": "group:default/team-orders"}

failures = 0


def call(method: str, url: str, headers: dict | None = None, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, parse(res.read())
    except urllib.error.HTTPError as err:
        return err.code, parse(err.read())


def parse(raw: bytes) -> object:
    """JSON when the body is JSON (APIs), otherwise text (e.g. Backstage's healthcheck)."""
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw.decode(errors="replace")


def check(name: str, ok: bool, detail: object = "") -> None:
    global failures
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    failures += not ok


print("== services")
status, _ = call("GET", f"{BACKSTAGE}/healthcheck")
check("Backstage healthcheck", status == 200, status)
status, _ = call("GET", f"{DISCOVERY}/readyz")
check("discovery ready", status == 200, status)
status, _ = call("GET", f"{ORCHESTRATOR}/readyz")
check("orchestrator ready", status == 200, status)

print("== discovery: approved resources")
status, subs = call("GET", f"{DISCOVERY}/v1/subscriptions?environment=dev", SERVICE)
check("dev subscription listed", status == 200 and any(s["id"] == SUB for s in subs), subs)
status, clusters = call("GET", f"{DISCOVERY}/v1/subscriptions/{SUB}/aks-clusters?environment=dev", SERVICE)
domain = clusters[0].get("base_domain") if status == 200 and clusters else None
check("cluster carries the gateway domain", domain == "dev.xycorp.local", clusters)

print("== orchestrator: golden-path request with the platform defaults")
name = f"e2e-{uuid.uuid4().hex[:8]}"
body = {
    "idempotency_key": f"e2e-{uuid.uuid4()}",
    "application_name": name,
    "description": "Local end-to-end check",
    "owner": "group:default/team-orders",
    "environment": "dev",
    "region": "uksouth",
    "stack": "nestjs",
    "subscription": {"mode": "existing", "id": SUB},
    "resource_group": {"mode": "existing", "name": "rg-idp-apps-dev"},
    "aks_cluster": {"mode": "existing", "name": "aks-idp-shared-dev"},
    "container_registry": {"mode": "existing", "name": "acridpdev"},
    "namespace": {"mode": "new", "name": name},
    "runtime_capability": {"type": "storage", "mode": "existing", "name": "stidpshareddev"},
    "availability": {"tier": "standard"},
    "endpoint_host": "",
}
status, req = call("POST", f"{ORCHESTRATOR}/v1/requests", REQUESTER, body)
check("request accepted", status == 201, req)
if status == 201:
    rid = req["id"]
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        _, req = call("GET", f"{ORCHESTRATOR}/v1/requests/{rid}", SERVICE)
        if req["ready_for_repository"] or req["state"] in ("FAILED", "CANCELLED"):
            break
        time.sleep(2)
    check("validated by discovery (worker)", req["ready_for_repository"], f"{req['state']}: {req.get('validation')}")
    check("endpoint host defaulted", req.get("endpoint_host") == f"{name}.dev.xycorp.local", req.get("endpoint_host"))
    status, _ = call("POST", f"{ORCHESTRATOR}/v1/requests/{rid}/cancel", REQUESTER, {})
    check("request cancelled (cleanup)", status == 200, status)

print(f"== {'all checks passed' if not failures else f'{failures} check(s) failed'}")
sys.exit(1 if failures else 0)
