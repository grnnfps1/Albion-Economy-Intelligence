"""Lock distribuído no Redis.

Dois collectors do mesmo servidor rodando ao mesmo tempo não duplicam dado --
o upsert cuida disso -- mas **dobram o consumo de rate limit**, e o orçamento é
de 1 req/s. O lock existe para proteger a cota, não a integridade.

Implementação: SET NX PX com token aleatório, e liberação condicional por script
Lua. Sem o token, um processo lento libera o lock que outro já adquiriu.
"""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from app.cache.redis import LOCK_PREFIX
from app.core.logging import get_logger

log = get_logger(__name__)

# Só apaga se o token ainda for o nosso.
_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""


class LockNotAcquired(RuntimeError):
    """Outro processo já está com o lock."""


class RedisLock:
    def __init__(self, redis: Redis, name: str, ttl_seconds: int = 900) -> None:
        self.redis = redis
        self.key = f"{LOCK_PREFIX}:{name}"
        self.ttl_seconds = ttl_seconds
        self._token = secrets.token_hex(16)

    async def acquire(self) -> bool:
        acquired = await self.redis.set(
            self.key, self._token, nx=True, px=self.ttl_seconds * 1000
        )
        return bool(acquired)

    async def release(self) -> bool:
        released = await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self._token)
        return bool(released)

    async def extend(self) -> bool:
        """Renova o TTL se o lock ainda for nosso. Para jobs que passam do previsto."""
        current = await self.redis.get(self.key)
        if current != self._token:
            return False
        await self.redis.pexpire(self.key, self.ttl_seconds * 1000)
        return True


@asynccontextmanager
async def collector_lock(
    redis: Redis, name: str, ttl_seconds: int = 900
) -> AsyncIterator[RedisLock]:
    """Levanta LockNotAcquired quando outro processo já está rodando.

    O TTL evita que um processo morto trave a coleta para sempre: o lock expira
    sozinho. Por isso o TTL precisa ser maior que a duração esperada do job.
    """
    lock = RedisLock(redis, name, ttl_seconds)
    if not await lock.acquire():
        raise LockNotAcquired(f"collector já em execução: {name}")
    log.info("lock adquirido", lock=name, ttl_seconds=ttl_seconds)
    try:
        yield lock
    finally:
        await lock.release()
        log.info("lock liberado", lock=name)
