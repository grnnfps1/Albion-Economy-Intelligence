"""Dashboard: integra tudo sem virar vitrine."""

from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.aodp.normalization import MarketPriceRecord
from app.core.config import Settings
from app.core.freshness import Freshness
from app.models.catalog import Item
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.dashboard_service import build_dashboard

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)
SETTINGS = Settings(freshness_fresh_seconds=900, freshness_stale_seconds=21600)

COM_TAXAS = dict(
    return_rate=0.15, station_fee_per_100_nutrition=1000,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
)
SEM_TAXAS = dict(
    return_rate=None, station_fee_per_100_nutrition=None,
    setup_fee_pct=None, sales_tax_pct=None, premium=None,
)
BASE = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    focus_budget=10_000, horizon_days=7,
)


@pytest.fixture
async def mundo(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    lymhurst = Location(aodp_name="Lymhurst", slug="lymhurst",
                        display_name="Lymhurst", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    couro = Item(unique_name="T5_LEATHER", base_name="T5_LEATHER", tier=5, enchantment=0,
                 display_name_pt="Couro Curtido", subcategory_code="refinedresources",
                 item_value=32, is_tracked=True)
    session.add_all([server, caerleon, lymhurst, source, couro])
    await session.flush()

    async def semear(idade_minutos: int = 5):
        quando = AGORA - timedelta(minutes=idade_minutos)
        await market_repo.upsert_prices(session, [
            MarketPriceRecord(
                server_id=server.id, location_id=local.id, item_id=couro.id, quality=2,
                sell_price_min=preco, sell_price_min_date=quando,
                sell_price_max=preco, sell_price_max_date=quando,
                buy_price_min=None, buy_price_min_date=None,
                buy_price_max=int(preco * 0.95), buy_price_max_date=quando,
                observed_at=quando, source_id=source.id,
            )
            for local, preco in ((caerleon, 1200), (lymhurst, 1900))
        ])
        await session.flush()

    return {"semear": semear}


async def test_pipeline_vem_antes_dos_numeros(session, mundo):
    await mundo["semear"](idade_minutos=5)
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    assert resposta.pipeline.prices_tracked == 2
    assert resposta.pipeline.freshness is Freshness.FRESH
    assert resposta.pipeline.stale_price_ratio == 0.0


async def test_coleta_parada_e_reportada(session, mundo):
    """Se o collector parou, todos os cards olham um retrato antigo."""
    await mundo["semear"](idade_minutos=60 * 20)
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    assert resposta.pipeline.freshness is Freshness.OLD
    assert resposta.pipeline.stale_price_ratio == 1.0


async def test_quatro_cards_sempre_presentes(session, mundo):
    """Card indisponível é informação; card sumido é buraco sem explicação."""
    await mundo["semear"]()
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    assert [card.kind for card in resposta.cards] == [
        "ARBITRAGEM", "CRAFTING", "REFINO", "FOCUS"
    ]


async def test_sem_taxas_os_cards_explicam_o_motivo(session, mundo):
    await mundo["semear"]()
    resposta = await build_dashboard(session, SETTINGS, **BASE, **SEM_TAXAS)

    assert all(card.available is False for card in resposta.cards)
    assert all(card.reason for card in resposta.cards)
    assert resposta.top_opportunities == []


async def test_card_carrega_idade_e_confianca(session, mundo):
    """Headline sozinho seria vitrine."""
    await mundo["semear"]()
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    arbitragem = next(c for c in resposta.cards if c.kind == "ARBITRAGEM")
    assert arbitragem.available is True
    assert arbitragem.headline is not None
    assert arbitragem.headline_label
    assert arbitragem.age_seconds is not None
    assert arbitragem.freshness is Freshness.FRESH
    assert arbitragem.confidence is not None


async def test_top_so_entra_com_score_calculado(session, mundo):
    await mundo["semear"]()
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    assert all(card.score is not None for card in resposta.top_opportunities)
    assert all(card.freshness is not Freshness.UNKNOWN for card in resposta.top_opportunities)


async def test_sem_dado_nenhum_nao_estoura(session, mundo):
    resposta = await build_dashboard(session, SETTINGS, **BASE, **COM_TAXAS)

    assert resposta.pipeline.prices_tracked == 0
    assert resposta.pipeline.last_collection_age_seconds is None
    assert all(card.available is False for card in resposta.cards)
