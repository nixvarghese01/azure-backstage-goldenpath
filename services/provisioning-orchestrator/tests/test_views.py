"""The Provisioning tab's links: web URLs people can open, on the platform's scheme."""

from types import SimpleNamespace

from provisioning_orchestrator.views import urls


def _req(**kw):
    base = {
        "application_name": "orders-api",
        "deployment": {},
        "spec": {"endpoint_host": "orders-api.4.223.242.50.nip.io"},
        "repository": {"url": "https://github.com/nixvarghese01/orders-api.git"},
        "application": {},
        "platform": {},
        "validation": {},
    }
    return SimpleNamespace(**{**base, **kw})


def test_repository_links_are_web_urls_not_the_clone_url() -> None:
    u = urls(_req(), "http://idp-dev.example")
    assert u["repository"] == "https://github.com/nixvarghese01/orders-api"
    assert u["workflow_runs"] == "https://github.com/nixvarghese01/orders-api/actions"


def test_backstage_link_uses_the_public_url() -> None:
    u = urls(_req(), "http://idp-dev.example")
    assert u["backstage"] == "http://idp-dev.example/catalog/default/component/orders-api"


def test_application_links_follow_the_gateway_scheme() -> None:
    deployed = _req(deployment={"endpoint": "orders-api.4.223.242.50.nip.io"})
    assert urls(deployed, "http://b", "http")["application"] == "http://orders-api.4.223.242.50.nip.io"
    assert urls(deployed, "http://b", "https")["api_docs"] == "https://orders-api.4.223.242.50.nip.io/docs"


def test_unregister_removes_the_location_before_the_entity(monkeypatch) -> None:
    import provisioning_orchestrator.clients.backstage as bs

    calls: list[tuple[str, str]] = []

    class Res:
        def __init__(self, code: int, body: dict | None = None) -> None:
            self.status_code, self._body = code, body or {}

        def json(self) -> dict:
            return self._body

        def raise_for_status(self) -> None:
            assert self.status_code < 400

    def get(url: str, **_: object) -> Res:
        calls.append(("GET", url))
        return Res(200, {"id": "loc-1"} if "/locations/" in url else {"metadata": {"uid": "uid-1"}})

    def delete(url: str, **_: object) -> Res:
        calls.append(("DELETE", url))
        return Res(204)

    monkeypatch.setattr(bs, "bearer_for", lambda scope: "t")
    monkeypatch.setattr(bs.httpx, "get", get)
    monkeypatch.setattr(bs.httpx, "delete", delete)
    bs.HttpBackstageClient("http://b", "scope").unregister_component("orders-api")
    deletes = [u for m, u in calls if m == "DELETE"]
    assert deletes == ["http://b/api/catalog/locations/loc-1", "http://b/api/catalog/entities/by-uid/uid-1"]
