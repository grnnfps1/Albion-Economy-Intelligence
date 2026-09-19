"""Ranking de Focus ponta a ponta."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.focus_service import build_focus_ranking

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)

PADRAO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    focus_budget=10_000, horizon_days=7,
    return_rate=0.15, station_fee_per_100_nutrition=1000, spec_levels=None, spec_item_levels=None,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    sourcing=Sourcing.CHEAPEST, strategy=Strategy.FAST,
    sort_by="realizable_profit", limit=30,
)


@pytest.fixture
async def mundo(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    session.add_all([server, caerleon, source])
    await session.flush()

    itens = {
        "T4_WOOD": ("resources", 4), "T5_WOOD": ("resources", 5),
        "T4_PLANKS": ("refinedresources", 4), "T5_PLANKS": ("refinedresources", 5),
        "T3_PLANKS": ("refinedresources", 3),
    }
    criados = {}
    for nome, (sub, tier) in itens.items():
        criados[nome] = Item(
            unique_name=nome, base_name=nome, tier=tier, enchantment=0,
            display_name_pt=nome, subcategory_code=sub,
            # Dobra a cada tier, como no dump: é o que move a taxa da estação.
            item_value=2 ** tier, is_tracked=True,
        )
    session.add_all(criados.values())
    await session.flush()

    for tier in (4, 5):
        receita = Recipe(
            output_item_id=criados[f"T{tier}_PLANKS"].id, variant_index=0,
            output_quantity=1, focus_cost=tier * 20, silver_cost=0,
            station_category="wood",
        )
        session.add(receita)
        await session.flush()
        session.add_all([
            RecipeMaterial(recipe_id=receita.id, item_id=criados[f"T{tier}_WOOD"].id,
                           quantity=2, is_returnable=True),
            RecipeMaterial(recipe_id=receita.id, item_id=criados[f"T{tier - 1}_PLANKS"].id,
                           quantity=1, is_returnable=True),
        ])
    await session.flush()

    quando = AGORA - timedelta(minutes=5)

    async def semear(precos):
        await market_repo.upsert_prices(session, [
            MarketPriceRecord(
                server_id=server.id, location_id=caerleon.id, item_id=criados[nome].id,
                quality=1, sell_price_min=preco, sell_price_min_date=quando,
                sell_price_max=preco, sell_price_max_date=quando,
                buy_price_min=None, buy_price_min_date=None,
                buy_price_max=max(1, int(preco * 0.9)), buy_price_max_date=quando,
                observed_at=AGORA, source_id=source.id,
            )
            for nome, preco in precos.items()
        ])
        await session.flush()

    return {"itens": criados, "semear": semear}


PRECOS = {"T4_WOOD": 300, "T5_WOOD": 900, "T3_PLANKS": 400,
          "T4_PLANKS": 1100, "T5_PLANKS": 4200}


async def test_ranking_reune_craft_e_refino(session, mundo):
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(session, **PADRAO)

    assert resposta.total > 0
    rotas = {plano.route for plano in resposta.plans}
    assert rotas <= {"CRAFTING", "REFINO"}


async def test_item_aparece_uma_vez_so(session, mundo):
    """Craft e refino podem produzir o mesmo item; fica a melhor rota."""
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(session, **PADRAO)

    nomes = [plano.item for plano in resposta.plans]
    assert len(nomes) == len(set(nomes))


async def test_orcamento_de_focus_limita_as_unidades(session, mundo):
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(session, **(PADRAO | {"focus_budget": 200}))

    for plano in resposta.plans:
        if plano.focus_used is not None:
            assert plano.focus_used <= 200 + 1e-6


async def test_ganho_realizavel_e_diferente_da_taxa(session, mundo):
    """A taxa é rendimento por ponto; o ganho é o que cabe nos dois tetos."""
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(session, **PADRAO)

    plano = resposta.plans[0]
    assert plano.profit_per_focus is not None
    assert plano.realizable_profit is not None
    assert plano.realizable_profit != plano.profit_per_focus


async def test_sem_parametros_nao_ha_ranking(session, mundo):
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(
        session, **(PADRAO | {"return_rate": None, "station_fee_per_100_nutrition": None,
                              "setup_fee_pct": None, "sales_tax_pct": None})
    )
    assert resposta.params.complete is False
    assert resposta.total == 0


async def test_liquidez_desconhecida_e_reportada(session, mundo):
    """Sem histórico não há giro; o limitador fica DESCONHECIDO."""
    await mundo["semear"](PRECOS)
    resposta = await build_focus_ranking(session, **PADRAO)

    assert all(plano.limiter in ("FOCUS", "LIQUIDEZ", "DESCONHECIDO")
               for plano in resposta.plans)
    assert any(plano.limiter == "DESCONHECIDO" for plano in resposta.plans)


async def test_ordenacao_por_taxa_muda_a_lista(session, mundo):
    await mundo["semear"](PRECOS)
    por_ganho = await build_focus_ranking(session, **PADRAO)
    por_taxa = await build_focus_ranking(
        session, **(PADRAO | {"sort_by": "profit_per_focus"})
    )
    assert por_ganho.sort_by == "realizable_profit"
    assert por_taxa.sort_by == "profit_per_focus"
