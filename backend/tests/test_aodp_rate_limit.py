"""Rate limiter de janela dupla.

Relógio e espera são falsos: dá para verificar o comportamento de 5 minutos em
milissegundos, e o teste é determinístico.
"""

import pytest

from app.collectors.aodp.rate_limit import (
    SlidingWindowRateLimiter,
    Window,
    compute_backoff,
    default_windows,
    parse_retry_after,
)


class FakeClock:
    """Relógio que só avança quando o limiter manda dormir."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def build(limiter_windows, clock):
    return SlidingWindowRateLimiter(limiter_windows, clock=clock, sleep=clock.sleep)


async def test_libera_ate_o_limite_sem_esperar():
    clock = FakeClock()
    limiter = build([Window(3, 60.0)], clock)

    for _ in range(3):
        assert await limiter.acquire() == 0.0
    assert clock.sleeps == []


async def test_espera_a_janela_abrir():
    clock = FakeClock()
    limiter = build([Window(2, 60.0)], clock)

    await limiter.acquire()
    await limiter.acquire()
    waited = await limiter.acquire()

    assert waited == pytest.approx(60.0)
    assert clock.now == pytest.approx(60.0)


async def test_janela_de_5_minutos_e_o_limite_que_manda():
    """180/min permite um pico; 300/5min é o teto real de 1 req/s sustentado.

    Implementar só a janela de 1 minuto passa em teste curto e toma 429 no
    minuto três. É este teste que impede essa regressão.
    """
    clock = FakeClock()
    limiter = build(default_windows(per_minute=180, per_5_minutes=300), clock)

    # Pico de 180 no primeiro minuto: a janela curta é respeitada.
    for _ in range(180):
        assert await limiter.acquire() == 0.0

    # Restam 120 na janela de 5 minutos. Depois disso, tem que esperar --
    # mesmo com a janela de 1 minuto já renovada.
    clock.now += 61.0
    for _ in range(120):
        assert await limiter.acquire() == 0.0

    assert await limiter.acquire() > 0.0


async def test_requisicoes_antigas_saem_da_janela():
    clock = FakeClock()
    limiter = build([Window(2, 60.0)], clock)

    await limiter.acquire()
    await limiter.acquire()
    clock.now += 61.0

    assert await limiter.acquire() == 0.0


async def test_janela_invalida_falha_alto():
    with pytest.raises(ValueError):
        Window(0, 60.0)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter([])


class TestBackoff:
    def test_cresce_exponencialmente(self):
        sem_jitter = lambda: 1.0  # noqa: E731
        assert compute_backoff(1, base_seconds=1, jitter=sem_jitter) == 1.0
        assert compute_backoff(2, base_seconds=1, jitter=sem_jitter) == 2.0
        assert compute_backoff(3, base_seconds=1, jitter=sem_jitter) == 4.0

    def test_respeita_o_teto(self):
        assert compute_backoff(20, base_seconds=1, cap_seconds=30, jitter=lambda: 1.0) == 30.0

    def test_jitter_espalha_os_retornos(self):
        """Sem jitter, workers que tomaram 429 juntos voltam juntos."""
        assert compute_backoff(3, base_seconds=1, jitter=lambda: 0.0) == 0.0
        assert compute_backoff(3, base_seconds=1, jitter=lambda: 0.5) == 2.0

    def test_tentativa_zero_e_erro_de_programacao(self):
        with pytest.raises(ValueError):
            compute_backoff(0)


class TestRetryAfter:
    def test_le_segundos(self):
        assert parse_retry_after("30") == 30.0
        assert parse_retry_after(" 5 ") == 5.0

    def test_ausente_ou_invalido_devolve_none(self):
        assert parse_retry_after(None) is None
        assert parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
        assert parse_retry_after("-1") is None
