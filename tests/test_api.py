from fastapi.testclient import TestClient

from src.api.backend.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_forecast_endpoint():
    client = TestClient(app)
    response = client.post("/api/forecast", json={"date": "2026-01-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-01-01"
    assert len(body["hourly_forecast"]) == 24
