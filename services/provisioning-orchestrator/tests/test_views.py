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
