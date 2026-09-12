"""Ping de disponibilidade do AODP.

FASE 1 apenas. O client completo (batch, retry, rate limiter, cache, parsing)
é a FASE 3 e mora em app/collectors/. Este módulo faz uma requisição pequena e
barata para responder "a fonte está de pé?" -- nada mais.
"""

import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings

# Endpoint mais barato disponível: uma única cotação de gold.
PING_PATH = "/api/v2/stats/gold.json?count=1"


@dataclass(frozen=True)
class AodpPingResult:
    server: str
    reachable: bool
    status_code: int | None
    latency_ms: int | None
    detail: str | None = None


async def ping(settings: Settings, server_code: str, client: httpx.AsyncClient) -> AodpPingResult:
    url = f"{settings.aodp_base_url(server_code)}{PING_PATH}"
    started = time.perf_counter()
    try:
        response = await client.get(
            url,
            timeout=settings.aodp_timeout_seconds,
            headers={
                "User-Agent": settings.aodp_user_agent,
                "Accept-Encoding": "gzip",
            },
        )
    except httpx.HTTPError as exc:
        return AodpPingResult(
            server=server_code,
            reachable=False,
            status_code=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            detail=type(exc).__name__,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code == 429:
        return AodpPingResult(server_code, False, 429, latency_ms, "rate limited")
    return AodpPingResult(
        server=server_code,
        reachable=response.is_success,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
