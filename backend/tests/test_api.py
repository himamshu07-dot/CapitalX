import pytest
from starlette.testclient import TestClient
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CapitalX" in data["service"]


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_validation_insufficient_tickers(client):
    # Only 1 ticker provided should fail validation
    payload = {
        "tickers": ["AAPL"],
        "lookback_years": 1
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 422
