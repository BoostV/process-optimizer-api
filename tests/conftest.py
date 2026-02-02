"""
pytest fixtures for FastAPI TestClient testing.
"""
import pytest
from fastapi.testclient import TestClient
from optimizerapi.server import app


@pytest.fixture
def client():
    """TestClient fixture for making HTTP requests to the app."""
    return TestClient(app)


@pytest.fixture
def auth_client():
    """TestClient fixture with API key authentication header."""
    return TestClient(app, headers={"X-API-Key": "test-key"})
