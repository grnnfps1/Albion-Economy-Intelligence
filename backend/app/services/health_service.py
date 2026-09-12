"""Health checks.

Separado das rotas porque o mesmo check é usado pelo endpoint HTTP, pelo
healthcheck do Docker e (mais tarde) pelo scheduler dos workers.
"""

import asyncio
import time

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.integrations.aodp import health as aodp_health
from app.schemas.health import AodpServerHealth, ComponentHealth


async def check_database(engine: AsyncEngine) -> ComponentHealth:
    started = time.perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health check reporta, não propaga
        return ComponentHealth(status="down", detail=type(exc).__name__)
    return ComponentHealth(status="ok", latency_ms=int((time.perf_counter() - started) * 1000))


async def check_cache(redis: Redis) -> ComponentHealth:
    started = time.perf_counter()
    try:
        await redis.ping()
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(status="down", detail=type(exc).__name__)
    return ComponentHealth(status="ok", latency_ms=int((time.perf_counter() - started) * 1000))


async def check_aodp(settings: Settings) -> list[AodpServerHealth]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(
            *(
                aodp_health.ping(settings, server_code, client)
                for server_code in settings.aodp_base_urls
            )
        )

    return [
        AodpServerHealth(
            server=result.server,
            status="ok" if result.reachable else "down",
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            detail=result.detail,
        )
        for result in results
    ]


def worst(statuses: list[str]) -> str:
    """Agrega status de componentes. O pior manda."""
    if not statuses:
        return "down"
    if all(s == "ok" for s in statuses):
        return "ok"
    if any(s == "ok" for s in statuses):
        return "degraded"
    return "down"
