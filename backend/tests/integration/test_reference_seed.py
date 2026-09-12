"""Conteúdo do seed de referência.

Roda contra o banco criado pelas MIGRATIONS (não pelos modelos), porque o que se
está verificando aqui é o resultado de `alembic upgrade head`.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio

MIGRATED_DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture
async def migrated_connection():
    if not MIGRATED_DATABASE_URL:
        pytest.skip("DATABASE_URL não definida; seed só é verificável no banco migrado")
    engine = create_async_engine(MIGRATED_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1 FROM alembic_version"))
            yield connection
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"banco migrado indisponível: {type(exc).__name__}")
    finally:
        await engine.dispose()


async def test_tres_servidores_com_hosts_do_aodp(migrated_connection):
    rows = (
        await migrated_connection.execute(
            text("SELECT code, aodp_base_url FROM servers ORDER BY code")
        )
    ).all()
    assert dict(rows) == {
        "east": "https://east.albion-online-data.com",
        "europe": "https://europe.albion-online-data.com",
        "west": "https://west.albion-online-data.com",
    }


async def test_black_market_nao_e_cidade(migrated_connection):
    """Requisito 31: Black Market existe, mas com kind próprio."""
    kind = await migrated_connection.scalar(
        text("SELECT kind FROM locations WHERE aodp_name = 'Black Market'")
    )
    assert kind == "black_market"

    cidades = await migrated_connection.scalar(
        text("SELECT count(*) FROM locations WHERE kind = 'royal_city'")
    )
    assert cidades == 7


async def test_nomes_de_local_batem_com_a_string_do_aodp(migrated_connection):
    """A chave de lookup é a string exata da API, com espaço e tudo."""
    nomes = set(
        (await migrated_connection.execute(text("SELECT aodp_name FROM locations"))).scalars()
    )
    assert "Fort Sterling" in nomes
    assert "Black Market" in nomes


async def test_fonte_aodp_marcada_como_comunitaria(migrated_connection):
    community = await migrated_connection.scalar(
        text("SELECT is_community_sourced FROM data_sources WHERE code = 'aodp'")
    )
    assert community is True


async def test_taxas_nao_verificadas_ficam_null_e_nao_zero(migrated_connection):
    """Requisito 52: sem valor confirmado, o parâmetro é UNKNOWN, não um chute."""
    rows = (
        await migrated_connection.execute(
            text(
                "SELECT key, value, source FROM config_parameters "
                "WHERE key LIKE 'market.%' OR key LIKE 'crafting.return_rate%'"
            )
        )
    ).all()
    assert rows, "parâmetros de taxa deveriam existir no seed"
    for key, value, source in rows:
        assert value is None, f"{key} não pode ter valor inventado"
        assert source == "UNKNOWN"


async def test_pesos_do_score_sao_configuraveis(migrated_connection):
    """Requisito 20: os pesos ficam em configuração, não dentro da fórmula."""
    weights = await migrated_connection.scalar(
        text("SELECT value FROM config_parameters WHERE key = 'score.weights'")
    )
    assert set(weights) == {
        "profit", "margin", "roi", "freshness", "liquidity", "trend", "distance", "risk"
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-9
