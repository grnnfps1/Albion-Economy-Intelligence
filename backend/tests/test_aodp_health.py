"""O client real é a FASE 3. Aqui só o ping de disponibilidade, com HTTP mockado."""

import httpx
import pytest
import respx

from app.core.config import Settings
from app.integrations.aodp.health import ping

GOLD_URL = "https://west.albion-online-data.com/api/v2/stats/gold.json"


@respx.mock
async def test_ping_ok(settings: Settings):
    respx.get(url__startswith=GOLD_URL).mock(
        return_value=httpx.Response(200, json=[{"price": 8000, "timestamp": "2026-09-12T21:00:00"}])
    )
    async with httpx.AsyncClient() as client:
        result = await ping(settings, "west", client)

    assert result.reachable is True
    assert result.status_code == 200
    assert result.latency_ms is not None


@respx.mock
async def test_ping_identifica_rate_limit(settings: Settings):
    """429 não é 'fonte fora do ar' -- é 'estamos pedindo demais' (requisito 16)."""
    respx.get(url__startswith=GOLD_URL).mock(return_value=httpx.Response(429))
    async with httpx.AsyncClient() as client:
        result = await ping(settings, "west", client)

    assert result.reachable is False
    assert result.status_code == 429
    assert result.detail == "rate limited"


@respx.mock
async def test_ping_trata_timeout_sem_estourar(settings: Settings):
    respx.get(url__startswith=GOLD_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
    async with httpx.AsyncClient() as client:
        result = await ping(settings, "west", client)

    assert result.reachable is False
    assert result.status_code is None
    assert result.detail == "ConnectTimeout"


@respx.mock
async def test_ping_envia_user_agent_e_gzip(settings: Settings):
    route = respx.get(url__startswith=GOLD_URL).mock(return_value=httpx.Response(200, json=[]))
    async with httpx.AsyncClient() as client:
        await ping(settings, "west", client)

    request = route.calls[0].request
    assert request.headers["user-agent"] == settings.aodp_user_agent
    assert "gzip" in request.headers["accept-encoding"]


async def test_ping_recusa_servidor_desconhecido(settings: Settings):
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await ping(settings, "inexistente", client)
