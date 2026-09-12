"""Endpoints de health com as dependências substituídas por dublês."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.api.v1.routes import health as health_routes
from app.main import create_app
from app.services import health_service


class _FakeRedis:
    def __init__(self, *, healthy: bool = True):
        self.healthy = healthy

    async def ping(self):
        if not self.healthy:
            raise ConnectionError("redis indisponível")
        return True


class _FakeConnection:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    async def execute(self, _statement):
        if not self.healthy:
            raise ConnectionError("banco indisponível")
        return None

    async def __aenter__(self):
        if not self.healthy:
            raise ConnectionError("banco indisponível")
        return self

    async def __aexit__(self, *_exc):
        return False


class _FakeEngine:
    def __init__(self, *, healthy: bool = True):
        self.healthy = healthy

    def connect(self):
        return _FakeConnection(self.healthy)


@pytest.fixture
def client(monkeypatch):
    """App sem lifespan: não abre conexão real com PG nem Redis."""
    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    monkeypatch.setattr(health_routes, "get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(health_routes, "get_redis", lambda: _FakeRedis())
    with TestClient(app) as test_client:
        yield test_client


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


def test_health_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"
    assert body["mock_data"] is False


def test_health_database_ok(client):
    response = client.get("/health/database")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["cache"]["status"] == "ok"


def test_health_database_retorna_503_quando_banco_cai(monkeypatch):
    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    monkeypatch.setattr(health_routes, "get_engine", lambda: _FakeEngine(healthy=False))
    monkeypatch.setattr(health_routes, "get_redis", lambda: _FakeRedis())
    with TestClient(app) as test_client:
        response = test_client.get("/health/database")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"      # redis vivo, banco morto
    assert body["database"]["status"] == "down"


@respx.mock
def test_health_aodp_agrega_os_tres_servidores(client):
    respx.get(url__regex=r".*albion-online-data\.com.*").mock(
        return_value=httpx.Response(200, json=[{"price": 8000, "timestamp": "2026-09-12T21:00:00"}])
    )
    response = client.get("/health/aodp")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["community_sourced"] is True
    assert {server["server"] for server in body["servers"]} == {"west", "east", "europe"}


@respx.mock
def test_health_aodp_503_quando_todos_caem(client):
    respx.get(url__regex=r".*albion-online-data\.com.*").mock(
        side_effect=httpx.ConnectError("sem rede")
    )
    response = client.get("/health/aodp")
    assert response.status_code == 503
    assert response.json()["status"] == "down"


def test_openapi_gerado(client):
    """Requisito 39: Swagger precisa existir desde o começo."""
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["ok", "ok"], "ok"),
        (["ok", "down"], "degraded"),
        (["down", "down"], "down"),
        ([], "down"),
    ],
)
def test_agregacao_de_status(statuses, expected):
    assert health_service.worst(statuses) == expected
