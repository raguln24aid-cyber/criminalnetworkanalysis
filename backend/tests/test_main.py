"""Smoke test: confirm the FastAPI app boots and the root route responds."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_responds():
    response = client.get("/")
    assert response.status_code == 200
