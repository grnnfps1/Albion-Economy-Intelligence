"""Collector de mercado ponta a ponta: AODP mockado, Postgres e Redis reais."""

import os
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest
import respx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache.locks import LockNotAcquired, collector_lock
from app.collectors.market_collector import collect_market_prices
from app.core.config import Settings
from app.models.catalog import Item
from app.models.observability import CollectorRun, RawResponse
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo

pytestmark = pytest.mark.asyncio

PRICES_URL = "https://west.albion-online-data.com/api/v2/stats/prices/"

PAYLOAD = [
    {
        "item_id": "T5_LEATHER", "city": "Caerleon", "quality": 2,
        "sell_price_min": 1200, "sell_price_min_date": "2026-09-12T11:50:00",
        "sell_price_max": 1250, "sell_price_max_date": "2026-09-12T11:50:00",
        "buy_price_min": 0, "buy_price_min_date": "0001-01-01T00:00:00",
        "buy_price_max": 1100, "buy_price_max_date": "2026-09-12T11:40:00",
    },
    {
        "item_id": "T5_LEATHER", "city": "Lymhurst", "quality": 2,
        "sell_price_min": 1650, "sell_price_min_date": "2026-09-12T11:55:00",
        "sell_price_max": 1700, "sell_price_max_date": "2026-09-12T11:55:00",
        "buy_price_min": 0, "buy_price_min_date": "0001-01-01T00:00:00",
        "buy_price_max": 0, "buy_price_max_date": "0001-01-01T00:00:00",
    },
    # Local que não está cadastrado: precisa ser rejeitado com contagem.
    {
        "item_id": "T5_LEATHER", "city": "Thetford Portal", "quality": 2,
        "sell_price_min": 1400, "sell_price_min_date": "2026-09-12T11:00:00",
        "sell_price_max": 1400, "sell_price_max_date": "2026-09-12T11:00:00",
        "buy_price_min": 0, "buy_price_min_date": "0001-01-01T00:00:00",
        "buy_price_max": 0, "buy_price_max_date": "0001-01-01T00:00:00",
    },
]


def _test_redis_url() -> str:
    """URL do Redis de teste, sempre no banco 15.

    O fixture roda `flushdb`, então não pode apontar para o banco da aplicação:
    rodar a suíte apagaria cache, janela de rate limit e locks de coleta. Fixar
    `localhost` também não serve — dentro do container o Redis atende em `redis`.
    """
    explicit = os.environ.get("TEST_REDIS_URL")
    if explicit:
        return explicit
    parts = urlsplit(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return urlunsplit(parts._replace(path="/15"))


TEST_REDIS_URL = _test_redis_url()


@pytest.fixture
async def redis_client():
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        await client.aclose()
        pytest.skip(f"Redis indisponível em {TEST_REDIS_URL}: {type(exc).__name__}")
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def seeded(engine):
    """Semeia num commit real: o collector abre sessões próprias."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                Server(code="west", display_name="Americas",
                       aodp_base_url="https://west.albion-online-data.com"),
                Location(aodp_name="Caerleon", slug="caerleon",
                         display_name="Caerleon", kind="royal_city"),
                Location(aodp_name="Lymhurst", slug="lymhurst",
                         display_name="Lymhurst", kind="royal_city"),
                DataSource(code="aodp", display_name="AODP", is_community_sourced=True),
                Item(unique_name="T5_LEATHER", base_name="T5_LEATHER", tier=5,
                     enchantment=0, display_name_pt="Couro Curtido", is_tracked=True),
            ]
        )
        await session.commit()

    yield factory

    async with factory() as session:
        for model in (RawResponse, CollectorRun):
            for row in (await session.scalars(select(model))).all():
                await session.delete(row)
        await session.commit()
        await session.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE market_prices, items, locations, servers, data_sources CASCADE"
            )
        )
        await session.commit()


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="development", aodp_timeout_seconds=2.0)


@respx.mock
async def test_coleta_grava_precos_normalizados(settings, seeded, redis_client):
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))

    async with httpx.AsyncClient() as http:
        result = await collect_market_prices(
            settings, seeded, redis_client, "west", http
        )

    assert result.status == "success"
    assert result.rows_received == 3
    assert result.rows_upserted == 2

    async with seeded() as session:
        rows, total = await market_repo.search_prices(session, "west")

    assert total == 2
    por_cidade = {location.slug: price for price, _item, location in rows}
    assert por_cidade["caerleon"].sell_price_min == 1200
    # Sentinela virou None, não zero (requisito 52).
    assert por_cidade["caerleon"].buy_price_min is None
    assert por_cidade["caerleon"].buy_price_max == 1100
    assert por_cidade["lymhurst"].buy_price_max is None


@respx.mock
async def test_local_desconhecido_e_contado_e_nao_gravado(settings, seeded, redis_client):
    """Uma portal city nova não pode virar linha órfã nem sumir em silêncio."""
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))

    async with httpx.AsyncClient() as http:
        result = await collect_market_prices(settings, seeded, redis_client, "west", http)

    assert result.rows_rejected == 1
    assert result.rejection_reasons == {"local desconhecido": 1}


@respx.mock
async def test_execucao_fica_registrada(settings, seeded, redis_client):
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))

    async with httpx.AsyncClient() as http:
        await collect_market_prices(settings, seeded, redis_client, "west", http)

    async with seeded() as session:
        run = await session.scalar(select(CollectorRun))
        raws = (await session.scalars(select(RawResponse))).all()

    assert run is not None
    assert run.collector == "market"
    assert run.status == "success"
    assert run.finished_at is not None
    assert run.rows_upserted == 2
    assert run.rows_rejected == 1
    assert len(raws) == 1
    assert len(raws[0].payload_sha256) == 64


@respx.mock
async def test_coleta_e_idempotente(settings, seeded, redis_client):
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))

    async with httpx.AsyncClient() as http:
        await collect_market_prices(settings, seeded, redis_client, "west", http)
        await collect_market_prices(settings, seeded, redis_client, "west", http)

    async with seeded() as session:
        assert await market_repo.count_prices(session, "west") == 2


@respx.mock
async def test_lote_que_falha_nao_derruba_a_coleta(settings, seeded, redis_client):
    """Perder um lote é melhor do que perder a varredura."""
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(500))

    async with httpx.AsyncClient() as http:
        result = await collect_market_prices(settings, seeded, redis_client, "west", http)

    assert result.status == "partial"
    assert result.failed_batches == 1

    async with seeded() as session:
        run = await session.scalar(select(CollectorRun))
    assert run.status == "partial"


@respx.mock
async def test_lock_impede_segunda_coleta_do_mesmo_servidor(settings, seeded, redis_client):
    """Duas coletas simultâneas dobram o consumo de rate limit."""
    respx.get(url__startswith=PRICES_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))

    async with collector_lock(redis_client, "market:west"):
        async with httpx.AsyncClient() as http:
            with pytest.raises(LockNotAcquired):
                await collect_market_prices(settings, seeded, redis_client, "west", http)


@respx.mock
async def test_servidor_fora_do_banco_falha_alto(settings, seeded, redis_client):
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="não cadastrado"):
            await collect_market_prices(settings, seeded, redis_client, "east", http)


async def test_lock_libera_apenas_o_proprio_token(redis_client):
    from app.cache.locks import RedisLock

    primeiro = RedisLock(redis_client, "market:west")
    segundo = RedisLock(redis_client, "market:west")

    assert await primeiro.acquire() is True
    assert await segundo.acquire() is False
    # Um processo lento não pode liberar o lock de outro.
    assert await segundo.release() is False
    assert await primeiro.release() is True
    assert await segundo.acquire() is True
