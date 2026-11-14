"""Verifica el contrato HTTP y la configuración de arranque."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.__main__ import load_bind

def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.parametrize("value", ["", "abc", "0", "65536"])
def test_invalid_port(monkeypatch, value):
    monkeypatch.setenv("ML_PORT", value)
    with pytest.raises(ValueError, match="ML_PORT"):
        load_bind()

def test_empty_host(monkeypatch):
    monkeypatch.setenv("ML_HOST", " ")
    with pytest.raises(ValueError, match="ML_HOST"):
        load_bind()

def test_valid_bind(monkeypatch):
    monkeypatch.setenv("ML_HOST", "127.0.0.1")
    monkeypatch.setenv("ML_PORT", "8100")
    assert load_bind() == ("127.0.0.1", 8100)
