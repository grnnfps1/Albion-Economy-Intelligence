"""Upsert e consulta de preços contra PostgreSQL de verdade."""

from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


@pytest.fixture
async def fixtures(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(
        aodp_name="Caerleon", slug="caerleon", display_name="Caerleon", kind="royal_city"
    )
    lymhurst = Location(
        aodp_name="Lymhurst", slug="lymhurst", display_name="Lymhurst", kind="royal_city"
    )
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    leather = Item(
        unique_name="T5_LEATHER", base_name="T5_LEATHER", tier=5, enchantment=0,
        display_name_pt="Couro Curtido", is_tracked=True,
    )
    bag = Item(
        unique_name="T4_BAG@1", base_name="T4_BAG", tier=4, enchantment=1,
        display_name_pt="Bolsa", is_tracked=False,
    )
    session.add_all([server, caerleon, lymhurst, source, leather, bag])
    await session.flush()
    return {
        "server": server, "caerleon": caerleon, "lymhurst": lymhurst,
        "source": source, "leather": leather, "bag": bag,
    }


def record(fixtures, item, location, **overrides) -> MarketPriceRecord:
    defaults = dict(
        server_id=fixtures["server"].id,
        location_id=location.id,
        item_id=item.id,
        quality=2,
        sell_price_min=1200, sell_price_min_date=NOW,
        sell_price_max=1300, sell_price_max_date=NOW,
        buy_price_min=None, buy_price_min_date=None,
        buy_price_max=None, buy_price_max_date=None,
        observed_at=NOW,
        source_id=fixtures["source"].id,
    )
    return MarketPriceRecord(**(defaults | overrides))


async def test_upsert_grava_e_atualiza_sem_duplicar(session, fixtures):
    leather, caerleon = fixtures["leather"], fixtures["caerleon"]

    assert await market_repo.upsert_prices(session, [record(fixtures, leather, caerleon)]) == 1
    assert await market_repo.count_prices(session, "west") == 1

    await market_repo.upsert_prices(
        session,
        [
            record(
                fixtures, leather, caerleon,
                sell_price_min=999, observed_at=NOW + timedelta(minutes=5),
            )
        ],
    )
    rows, total = await market_repo.search_prices(session, "west")

    assert total == 1
    assert rows[0][0].sell_price_min == 999


async def test_linha_sem_nenhum_preco_nao_e_gravada(session, fixtures):
    """'Ninguém abriu esse mercado' não é uma observação de preço."""
    vazio = record(
        fixtures, fixtures["leather"], fixtures["caerleon"],
        sell_price_min=None, sell_price_min_date=None,
        sell_price_max=None, sell_price_max_date=None,
    )
    assert await market_repo.upsert_prices(session, [vazio]) == 0
    assert await market_repo.count_prices(session, "west") == 0


async def test_mesma_chave_em_cidades_diferentes_sao_linhas_distintas(session, fixtures):
    await market_repo.upsert_prices(
        session,
        [
            record(fixtures, fixtures["leather"], fixtures["caerleon"]),
            record(fixtures, fixtures["leather"], fixtures["lymhurst"], sell_price_min=1650),
        ],
    )
    _, total = await market_repo.search_prices(session, "west")
    assert total == 2


async def test_qualidades_diferentes_nao_colidem(session, fixtures):
    await market_repo.upsert_prices(
        session,
        [
            record(fixtures, fixtures["leather"], fixtures["caerleon"], quality=1),
            record(fixtures, fixtures["leather"], fixtures["caerleon"], quality=2),
        ],
    )
    _, total = await market_repo.search_prices(session, "west")
    assert total == 2


async def test_filtros_de_busca(session, fixtures):
    await market_repo.upsert_prices(
        session,
        [
            record(fixtures, fixtures["leather"], fixtures["caerleon"]),
            record(fixtures, fixtures["bag"], fixtures["lymhurst"]),
        ],
    )

    _, por_cidade = await market_repo.search_prices(session, "west", location_slugs=["caerleon"])
    _, por_nome = await market_repo.search_prices(session, "west", item_search="couro")
    _, por_tier = await market_repo.search_prices(session, "west", tier=4)
    _, por_encanto = await market_repo.search_prices(session, "west", enchantment=1)
    _, rastreados = await market_repo.search_prices(session, "west", tracked_only=True)

    assert por_cidade == 1
    assert por_nome == 1
    assert por_tier == 1
    assert por_encanto == 1
    assert rastreados == 1


async def test_servidores_nao_se_misturam(session, fixtures):
    east = Server(code="east", display_name="Asia", aodp_base_url="https://y")
    session.add(east)
    await session.flush()

    await market_repo.upsert_prices(
        session, [record(fixtures, fixtures["leather"], fixtures["caerleon"])]
    )
    _, total_east = await market_repo.search_prices(session, "east")

    assert total_east == 0


async def test_ordenar_por_preco_nao_joga_sem_dado_para_o_topo(session, fixtures):
    """NULL significa 'sem ordem', não 'mais barato'."""
    await market_repo.upsert_prices(
        session,
        [
            record(fixtures, fixtures["leather"], fixtures["caerleon"], sell_price_min=1200),
            record(
                fixtures, fixtures["bag"], fixtures["lymhurst"],
                sell_price_min=None, sell_price_min_date=None,
            ),
        ],
    )

    rows, _ = await market_repo.search_prices(session, "west", sort_by="sell_price_min")

    assert rows[0][0].sell_price_min == 1200
    assert rows[-1][0].sell_price_min is None


async def test_freshest_observation(session, fixtures):
    assert await market_repo.freshest_observation(session, "west") is None
    await market_repo.upsert_prices(
        session, [record(fixtures, fixtures["leather"], fixtures["caerleon"])]
    )
    assert await market_repo.freshest_observation(session, "west") == NOW
