from fastapi.testclient import TestClient

from app.main import app


def test_starter_contract() -> None:
    with TestClient(app) as client:
        assert client.get("/health/ready").json()["status"] == "ok"
        assert client.get("/v1/orders").json()[0]["id"] == "demo-001"
        assert client.get("/docs").status_code == 200
        assert client.get("/missing").status_code == 404
