"""Rate limiter de janela dupla para o AODP.

O AODP documenta **dois** limites simultâneos:

    180 requisições / 1 minuto
    300 requisições / 5 minutos

O segundo é o que manda. 300 em 5 minutos são 1 req/s sustentado; quem dispara
180 no primeiro minuto fica com 120 para os quatro minutos seguintes e toma 429
no minuto três. Implementar só a janela de 1 minuto passa despercebido em teste
curto e quebra em produção.

Relógio e espera são injetados. Isso torna o comportamento verificável em teste
sem esperar minutos de verdade.
"""

import asyncio
import random
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    """Uma janela deslizante: `limit` requisições a cada `seconds`."""

    limit: int
    seconds: float

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.seconds <= 0:
            raise ValueError("janela precisa de limite e duração positivos")


class SlidingWindowRateLimiter:
    """Respeita todas as janelas configuradas ao mesmo tempo.

    Guarda os instantes das requisições recentes e, antes de liberar a próxima,
    calcula quanto falta para a janela mais restritiva abrir.
    """

    def __init__(
        self,
        windows: list[Window],
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if not windows:
            raise ValueError("é preciso ao menos uma janela")
        self._windows = sorted(windows, key=lambda w: w.seconds, reverse=True)
        self._longest = self._windows[0].seconds
        self._clock = clock or (lambda: asyncio.get_running_loop().time())
        self._sleep = sleep or asyncio.sleep
        self._hits: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self._longest
        while self._hits and self._hits[0] <= cutoff:
            self._hits.popleft()

    def _wait_needed(self, now: float) -> float:
        """Segundos a esperar para caber em todas as janelas. 0 = pode ir."""
        wait = 0.0
        for window in self._windows:
            start = now - window.seconds
            in_window = [hit for hit in self._hits if hit > start]
            if len(in_window) >= window.limit:
                # A requisição mais antiga dentro da janela é a que precisa sair.
                oldest = in_window[-window.limit]
                wait = max(wait, oldest + window.seconds - now)
        return wait

    async def acquire(self) -> float:
        """Bloqueia até poder requisitar. Devolve quanto tempo esperou."""
        async with self._lock:
            waited = 0.0
            while True:
                now = self._clock()
                self._prune(now)
                wait = self._wait_needed(now)
                if wait <= 0:
                    self._hits.append(now)
                    return waited
                await self._sleep(wait)
                waited += wait

    async def sleep(self, seconds: float) -> None:
        """Espera usando o mesmo relógio injetado no limiter.

        Existe para que backoff e rate limit compartilhem o relógio: em teste,
        um relógio falso adianta os dois juntos.
        """
        await self._sleep(seconds)

    def register_external_hit(self) -> None:
        """Contabiliza uma requisição feita fora do `acquire` (ex.: retry)."""
        self._hits.append(self._clock())


def default_windows(per_minute: int, per_5_minutes: int) -> list[Window]:
    return [Window(per_minute, 60.0), Window(per_5_minutes, 300.0)]


def compute_backoff(
    attempt: int,
    base_seconds: float = 1.0,
    cap_seconds: float = 60.0,
    jitter: Callable[[], float] = random.random,
) -> float:
    """Backoff exponencial com jitter total.

    Jitter não é enfeite: sem ele, vários workers que tomaram 429 juntos voltam
    juntos e tomam 429 de novo.
    """
    if attempt < 1:
        raise ValueError("attempt começa em 1")
    ceiling = min(cap_seconds, base_seconds * (2 ** (attempt - 1)))
    return ceiling * jitter()


def parse_retry_after(value: str | None) -> float | None:
    """Lê o header Retry-After em segundos.

    O servidor sabe melhor que o cliente quando voltar. Formato de data HTTP não
    é suportado -- devolve None e o chamador cai no backoff.
    """
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except (ValueError, AttributeError):
        return None
    return seconds if seconds >= 0 else None
