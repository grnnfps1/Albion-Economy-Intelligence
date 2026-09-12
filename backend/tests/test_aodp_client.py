"""Cliente do AODP com HTTP mockado.

Requisito 43: nenhum teste chama a API de verdade. As respostas abaixo são
recortes fiéis de payloads reais.
"""

import httpx
import pytest
import respx

from app.collectors.aodp.client import (
    AodpClient,
    AodpError,
    AodpInvalidPayload,
    AodpRateLimited,
)
from app.collectors.aodp.rate_limit import SlidingWindowRateLimiter, Window
from app.core.config import Settings

PRICES_URL = "https://west.albion-online-data.com/api/v2/stats/prices/"
HISTORY_URL = "https://west.albion-online-data.com/api/v2/stats/history/"
GOLD_URL = "https://west.albion-online-data.com/api/v2/stats/gold.json"

PRICE_PAYLOAD = [
    {
        "item_id": "T4_BAG",
        "city": "Caerleon",
        "quality": 2,
        "sell_price_min": 6388,
        "sell_price_min_date": "2026-09-10T00:30:00",
        "sell_price_max": 6486,
        "sell_price_max_date": "2026-09-10T00:30:00",
        "buy_price_min": 0,
        "buy_price_min_date": "0001-01-01T00:00:00",
        "buy_price_max": 0,
        "buy_price_max_date": "0001-01-01T00:00:00",
    }
]

HISTORY_PAYLOAD = [
    {
        "location": "Black Market",
        "item_id": "T4_BAG",
        "quality": 1,
        "data": [{"item_count": 424, "avg_price": 4425, "timestamp": "2026-08-13T00:00:00"}],
    }
]

GOLD_PAYLOAD = [{"price": 8000, "timestamp": "2026-09-12T21:00:00"}]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="development", aodp_timeout_seconds=2.0)


def make_client(settings, clock, http, **kwargs) -> AodpClient:
    limiter = SlidingWindowRateLimiter([Window(1000, 60.0)], clock=clock, sleep=clock.sleep)
    return AodpClient(settings, "west", http, redis=None, rate_limiter=limiter, **kwargs)


@respx.mock
async def test_fetch_prices_parseia_payload_real(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PRICE_PAYLOAD))

    async with httpx.AsyncClient() as http:
        rows, captures = await make_client(settings, clock, http).fetch_prices(
            ["T4_BAG"], locations=["Caerleon"], qualities=[2], use_cache=False
        )

    assert len(rows) == 1
    assert rows[0].item_id == "T4_BAG"
    assert rows[0].city == "Caerleon"
    assert rows[0].sell_price_min == 6388
    assert len(captures) == 1
    assert captures[0].endpoint == "prices"
    assert len(captures[0].payload_sha256) == 64


@respx.mock
async def test_requisicao_identifica_a_aplicacao_e_pede_gzip(settings, clock):
    """O AODP é comunitário e pede as duas coisas de quem consome em volume."""
    route = respx.get(url__startswith=PRICES_URL).mock(
        return_value=httpx.Response(200, json=PRICE_PAYLOAD)
    )

    async with httpx.AsyncClient() as http:
        await make_client(settings, clock, http).fetch_prices(["T4_BAG"], use_cache=False)

    request = route.calls[0].request
    assert request.headers["user-agent"] == settings.aodp_user_agent
    assert "gzip" in request.headers["accept-encoding"]


@respx.mock
async def test_muitos_itens_viram_varias_requisicoes_dentro_do_limite(settings, clock):
    route = respx.get(url__startswith=PRICES_URL).mock(
        return_value=httpx.Response(200, json=PRICE_PAYLOAD)
    )
    names = [f"T8_2H_HOLYSTAFF_MORGANA_VARIANT_{index}@3" for index in range(400)]

    async with httpx.AsyncClient() as http:
        client = make_client(settings, clock, http)
        await client.fetch_prices(names, locations=["Caerleon", "Fort Sterling"], use_cache=False)

    assert route.call_count > 1
    for call in route.calls:
        assert len(str(call.request.url)) <= settings.aodp_max_url_length
    assert client.stats.http_requests == route.call_count


@respx.mock
async def test_429_respeita_retry_after_e_depois_sucede(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=PRICE_PAYLOAD),
        ]
    )

    async with httpx.AsyncClient() as http:
        client = make_client(settings, clock, http)
        rows, _ = await client.fetch_prices(["T4_BAG"], use_cache=False)

    assert len(rows) == 1
    assert client.stats.rate_limited == 1
    assert client.stats.retries == 1
    # O servidor mandou esperar 7s; o cliente obedece em vez de usar o backoff.
    assert 7.0 in clock.sleeps


@respx.mock
async def test_429_persistente_falha_com_erro_proprio(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(429))

    async with httpx.AsyncClient() as http:
        client = make_client(settings, clock, http, max_attempts=3)
        with pytest.raises(AodpRateLimited):
            await client.fetch_prices(["T4_BAG"], use_cache=False)

    assert client.stats.rate_limited == 3
    assert client.stats.errors


@respx.mock
async def test_erro_5xx_e_repetido(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=PRICE_PAYLOAD)]
    )

    async with httpx.AsyncClient() as http:
        client = make_client(settings, clock, http)
        rows, _ = await client.fetch_prices(["T4_BAG"], use_cache=False)

    assert len(rows) == 1
    assert client.stats.retries == 1


@respx.mock
async def test_erro_4xx_nao_e_repetido(settings, clock):
    """400 é erro nosso: repetir só gasta a cota de quem está certo."""
    route = respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(400))

    async with httpx.AsyncClient() as http:
        with pytest.raises(AodpError):
            await make_client(settings, clock, http).fetch_prices(["T4_BAG"], use_cache=False)

    assert route.call_count == 1


@respx.mock
async def test_timeout_e_repetido(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(
        side_effect=[httpx.ConnectTimeout("timeout"), httpx.Response(200, json=PRICE_PAYLOAD)]
    )

    async with httpx.AsyncClient() as http:
        client = make_client(settings, clock, http)
        rows, _ = await client.fetch_prices(["T4_BAG"], use_cache=False)

    assert len(rows) == 1
    assert client.stats.retries == 1


@respx.mock
async def test_payload_fora_do_contrato_falha_alto_preservando_o_bruto(settings, clock):
    """Risco R8: aceitar formato diferente em silêncio grava dado errado."""
    quebrado = [{"item_id": "T4_BAG", "city": "Caerleon"}]
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=quebrado))

    async with httpx.AsyncClient() as http:
        with pytest.raises(AodpInvalidPayload) as exc:
            await make_client(settings, clock, http).fetch_prices(["T4_BAG"], use_cache=False)

    assert exc.value.payload == quebrado


@respx.mock
async def test_resposta_que_nao_e_lista_e_rejeitada(settings, clock):
    respx.get(url__startswith=PRICES_URL).mock(
        return_value=httpx.Response(200, json={"erro": "manutenção"})
    )

    async with httpx.AsyncClient() as http:
        with pytest.raises(AodpInvalidPayload):
            await make_client(settings, clock, http).fetch_prices(["T4_BAG"], use_cache=False)


@respx.mock
async def test_fetch_history_valida_timescale(settings, clock):
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="time-scale"):
            await make_client(settings, clock, http).fetch_history(["T4_BAG"], timescale=12)


@respx.mock
async def test_fetch_history_parseia_serie_aninhada(settings, clock):
    """O endpoint de histórico usa `location`, não `city`, e aninha os pontos."""
    route = respx.get(url__startswith=HISTORY_URL).mock(
        return_value=httpx.Response(200, json=HISTORY_PAYLOAD)
    )

    async with httpx.AsyncClient() as http:
        series, _ = await make_client(settings, clock, http).fetch_history(
            ["T4_BAG"], timescale=24, locations=["Black Market"], use_cache=False
        )

    assert series[0].location == "Black Market"
    assert series[0].data[0].avg_price == 4425
    assert "time-scale=24" in str(route.calls[0].request.url)


@respx.mock
async def test_fetch_gold(settings, clock):
    respx.get(url__startswith=GOLD_URL).mock(return_value=httpx.Response(200, json=GOLD_PAYLOAD))

    async with httpx.AsyncClient() as http:
        points, capture = await make_client(settings, clock, http).fetch_gold(
            count=1, use_cache=False
        )

    assert points[0].price == 8000
    assert capture is not None
    assert capture.endpoint == "gold"


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value


@respx.mock
async def test_cache_evita_segunda_requisicao(settings, clock):
    route = respx.get(url__startswith=PRICES_URL).mock(
        return_value=httpx.Response(200, json=PRICE_PAYLOAD)
    )
    redis = FakeRedis()

    async with httpx.AsyncClient() as http:
        limiter = SlidingWindowRateLimiter([Window(1000, 60.0)], clock=clock, sleep=clock.sleep)
        client = AodpClient(settings, "west", http, redis=redis, rate_limiter=limiter)
        await client.fetch_prices(["T4_BAG"], use_cache=True)
        rows, captures = await client.fetch_prices(["T4_BAG"], use_cache=True)

    assert route.call_count == 1
    assert client.stats.cache_hits == 1
    assert len(rows) == 1
    # Cache não gera captura: não houve resposta nova para auditar.
    assert captures == []


class BrokenRedis:
    async def get(self, key: str):
        raise ConnectionError("redis caiu")

    async def set(self, key: str, value: str, ex: int | None = None):
        raise ConnectionError("redis caiu")


@respx.mock
async def test_cache_indisponivel_nao_derruba_a_coleta(settings, clock):
    """Perder cache custa requisição; perder coleta custa o dia."""
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PRICE_PAYLOAD))

    async with httpx.AsyncClient() as http:
        limiter = SlidingWindowRateLimiter([Window(1000, 60.0)], clock=clock, sleep=clock.sleep)
        client = AodpClient(settings, "west", http, redis=BrokenRedis(), rate_limiter=limiter)
        rows, _ = await client.fetch_prices(["T4_BAG"], use_cache=True)

    assert len(rows) == 1


@respx.mock
async def test_rate_limiter_segura_o_ritmo(settings, clock):
    """Com 2 requisições por minuto, a terceira espera."""
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PRICE_PAYLOAD))

    async with httpx.AsyncClient() as http:
        limiter = SlidingWindowRateLimiter([Window(2, 60.0)], clock=clock, sleep=clock.sleep)
        client = AodpClient(settings, "west", http, rate_limiter=limiter)
        for _ in range(3):
            await client.fetch_prices(["T4_BAG"], use_cache=False)

    assert client.stats.waited_seconds > 0
    assert clock.now >= 60.0


async def test_servidor_desconhecido_falha_na_construcao(settings, clock):
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="servidor desconhecido"):
            AodpClient(settings, "brasil", http)
