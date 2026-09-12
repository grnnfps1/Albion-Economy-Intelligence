"""Cliente Redis.

Três namespaces com prefixos distintos para não colidirem:
  cache:v1:*         respostas de leitura
  rate:aodp:*        janelas do rate limiter do AODP
  lock:collector:*   lock distribuído de collector
"""

from redis.asyncio import Redis

from app.core.config import Settings

CACHE_PREFIX = "cache:v1"
RATE_PREFIX = "rate:aodp"
LOCK_PREFIX = "lock:collector"

_client: Redis | None = None


def init_redis(settings: Settings) -> Redis:
    global _client
    _client = Redis.from_url(
        str(settings.redis_url),
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    return _client


def get_redis() -> Redis:
    if _client is None:
        raise RuntimeError("redis não inicializado; chame init_redis() no startup")
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
