"""Read-only dummy FastAPI service. Replace samples with your application's business logic."""
from fastapi import FastAPI

app = FastAPI(title="Starter API", version="1.0.0")


@app.get("/")
def index() -> dict[str, str]:
    return {"service": "FastAPI starter", "docs": "/docs"}


@app.get("/health/live")
@app.get("/health/ready")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "demo"}


@app.get("/v1/orders")
def orders() -> list[dict[str, object]]:
    return [{"id": "demo-001", "customerId": "cust-001", "currency": "GBP", "total": 5}]
