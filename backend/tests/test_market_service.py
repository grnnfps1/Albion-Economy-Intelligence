"""Montagem da resposta de mercado: idade e frescor por campo."""

from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.freshness import Freshness
from app.models.catalog import Item
from app.models.market import MarketPrice
from app.models.reference import Location
from app.services.market_service import to_price_out

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
SETTINGS = Settings(freshness_fresh_seconds=900, freshness_stale_seconds=21600)

ITEM = Item(
    unique_name="T5_LEATHER", base_name="T5_LEATHER", tier=5, enchantment=0,
    display_name_pt="Couro Curtido", display_name_en="Cured Leather",
)
LOCATION = Location(
    aodp_name="Caerleon", slug="caerleon", display_name="Caerleon", kind="royal_city"
)


def build_price(**overrides) -> MarketPrice:
    defaults = dict(
        server_id=1, location_id=1, item_id=1, quality=2,
        sell_price_min=1200, sell_price_min_date=NOW - timedelta(minutes=8),
        sell_price_max=1300, sell_price_max_date=NOW - timedelta(minutes=8),
        buy_price_min=None, buy_price_min_date=None,
        buy_price_max=None, buy_price_max_date=None,
        observed_at=NOW - timedelta(minutes=2), source_id=1,
    )
    return MarketPrice(**(defaults | overrides))


def test_preco_com_idade_e_frescor():
    out = to_price_out(build_price(), ITEM, LOCATION, NOW, SETTINGS)
    assert out.sell_min.value == 1200
    assert out.sell_min.age_seconds == 480
    assert out.sell_min.freshness is Freshness.FRESH


def test_ausencia_de_ordem_nao_vira_zero():
    """Requisito 52: a UI precisa distinguir 'sem dado' de 'preço zero'."""
    out = to_price_out(build_price(), ITEM, LOCATION, NOW, SETTINGS)
    assert out.buy_max.value is None
    assert out.buy_max.age_seconds is None
    assert out.buy_max.freshness is Freshness.UNKNOWN


def test_cada_campo_tem_a_propria_idade():
    price = build_price(
        buy_price_max=1000, buy_price_max_date=NOW - timedelta(days=3)
    )
    out = to_price_out(price, ITEM, LOCATION, NOW, SETTINGS)
    assert out.sell_min.freshness is Freshness.FRESH
    assert out.buy_max.freshness is Freshness.OLD


def test_nome_visual_prefere_portugues_e_cai_para_ingles():
    out = to_price_out(build_price(), ITEM, LOCATION, NOW, SETTINGS)
    assert out.item_name == "Couro Curtido"

    sem_pt = Item(unique_name="T4_BAG", base_name="T4_BAG", tier=4, enchantment=0,
                  display_name_pt=None, display_name_en="Adept's Bag")
    assert to_price_out(build_price(), sem_pt, LOCATION, NOW, SETTINGS).item_name == "Adept's Bag"


def test_idade_da_coleta_e_separada_da_idade_da_cotacao():
    """Coletar agora um preço de ontem não torna o preço novo."""
    price = build_price(
        sell_price_min_date=NOW - timedelta(hours=3), observed_at=NOW
    )
    out = to_price_out(price, ITEM, LOCATION, NOW, SETTINGS)
    assert out.observed_freshness is Freshness.FRESH
    assert out.sell_min.freshness is Freshness.STALE
