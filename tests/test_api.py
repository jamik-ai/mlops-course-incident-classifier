from fastapi.testclient import TestClient
from src.api.backend.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Call Volume Forecast API. Use POST /api/forecast"