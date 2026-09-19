"""Refino ponta a ponta: cadeia de tiers contra PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.refining_service import family_of, find_refining_opportunities

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)

PADRAO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    sourcing=Sourcing.CHEAPEST, return_rate=0.15, station_fee_per_100_nutrition=1000,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    family=None, tier=None, strategy=Strategy.FAST, limit=40,
)


@pytest.fixture
async def cadeia(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    session.add_all([server, caerleon, source])
    await session.flush()

    itens = {}
    for tier in (2, 3, 4, 5):
        # `item_value` dobra a cada tier, como no dump. É o que faz a taxa da
        # estação do T5 ser 8× a do T2 — e por isso cada elo paga a sua.
        itens[f"T{tier}_WOOD"] = Item(
            unique_name=f"T{tier}_WOOD", base_name=f"T{tier}_WOOD", tier=tier, enchantment=0,
            display_name_pt=f"Madeira T{tier}", subcategory_code="resources",
            item_value=2 ** (tier - 1), is_tracked=True,
        )
        itens[f"T{tier}_PLANKS"] = Item(
            unique_name=f"T{tier}_PLANKS", base_name=f"T{tier}_PLANKS", tier=tier, enchantment=0,
            display_name_pt=f"Tábuas T{tier}", subcategory_code="refinedresources",
            item_value=2 ** tier, is_tracked=True,
        )
    session.add_all(itens.values())
    await session.flush()

    for tier in (3, 4, 5):
        receita = Recipe(
            output_item_id=itens[f"T{tier}_PLANKS"].id, variant_index=0, output_quantity=1,
            focus_cost=tier * 20, silver_cost=0, station_category="wood",
        )
        session.add(receita)
        await session.flush()
        session.add_all([
            RecipeMaterial(recipe_id=receita.id, item_id=itens[f"T{tier}_WOOD"].id,
                           quantity=2, is_returnable=True),
            RecipeMaterial(recipe_id=receita.id, item_id=itens[f"T{tier - 1}_PLANKS"].id,
                           quantity=1, is_returnable=True),
        ])
    await session.flush()

    quando = AGORA - timedelta(minutes=5)

    async def semear(precos: dict[str, int]):
        registros = [
            MarketPriceRecord(
                server_id=server.id, location_id=caerleon.id, item_id=itens[nome].id,
                quality=1, sell_price_min=preco, sell_price_min_date=quando,
                sell_price_max=preco, sell_price_max_date=quando,
                buy_price_min=None, buy_price_min_date=None,
                # Preço 0 viola o check de sentinela: preço zero e ausência de
                # ordem são coisas diferentes (requisito 52).
                buy_price_max=max(1, int(preco * 0.92)) if preco > 1 else None,
                buy_price_max_date=quando if preco > 1 else None,
                observed_at=AGORA, source_id=source.id,
            )
            for nome, preco in precos.items()
        ]
        await market_repo.upsert_prices(session, registros)
        await session.flush()

    return {"itens": itens, "semear": semear}


PRECOS = {
    "T2_WOOD": 50, "T3_WOOD": 120, "T4_WOOD": 300, "T5_WOOD": 900,
    "T2_PLANKS": 130, "T3_PLANKS": 400, "T4_PLANKS": 1100, "T5_PLANKS": 3800,
}


async def test_familia_extraida_do_identificador():
    assert family_of("T5_PLANKS") == "PLANKS"
    assert family_of("T5_PLANKS_LEVEL2@2") == "PLANKS"
    assert family_of("UNIQUE_HIDEOUT") is None


async def test_so_recursos_refinados_entram(session, cadeia):
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(session, **PADRAO)

    nomes = {o.item for o in resposta.opportunities}
    assert nomes == {"T2_PLANKS", "T3_PLANKS", "T4_PLANKS", "T5_PLANKS"}
    assert resposta.families == ["PLANKS"]


async def test_as_duas_alternativas_vao_na_resposta(session, cadeia):
    """Comprar pronto e produzir são respostas certas para pessoas diferentes."""
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(session, **PADRAO)

    t5 = next(o for o in resposta.opportunities if o.item == "T5_PLANKS")
    assert t5.cost_from_market == 3800
    assert t5.cost_from_crafting is not None
    assert t5.cost_from_crafting != t5.cost_from_market


async def test_cadeia_registra_cada_elo(session, cadeia):
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(
        session, **(PADRAO | {"sourcing": Sourcing.CRAFT})
    )

    t5 = next(o for o in resposta.opportunities if o.item == "T5_PLANKS")
    visitados = {passo.item for passo in t5.chain}
    assert {"T5_WOOD", "T4_PLANKS", "T3_PLANKS", "T2_PLANKS"} <= visitados
    assert t5.focus_per_unit > 0


async def test_mais_barato_compra_quando_o_mercado_desaba(session, cadeia):
    """Tier baixo costuma ter preço abaixo do custo de produção."""
    await cadeia["semear"]({**PRECOS, "T4_PLANKS": 1})
    resposta = await find_refining_opportunities(session, **PADRAO)

    t5 = next(o for o in resposta.opportunities if o.item == "T5_PLANKS")
    passo = next(p for p in t5.chain if p.item == "T4_PLANKS")
    assert passo.sourcing == "MERCADO"


async def test_sem_parametros_o_lucro_e_unknown(session, cadeia):
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(
        session, **(PADRAO | {"return_rate": None, "station_fee_per_100_nutrition": None,
                              "setup_fee_pct": None, "sales_tax_pct": None})
    )

    assert resposta.params.complete is False
    assert all(o.known is False for o in resposta.opportunities)
    assert all(o.profit is None for o in resposta.opportunities)


async def test_insumo_sem_cotacao_e_reportado(session, cadeia):
    await cadeia["semear"]({k: v for k, v in PRECOS.items() if k != "T3_WOOD"})
    resposta = await find_refining_opportunities(
        session, **(PADRAO | {"sourcing": Sourcing.CRAFT})
    )

    t5 = next(o for o in resposta.opportunities if o.item == "T5_PLANKS")
    assert t5.known is False
    assert "T3_WOOD" in t5.reason


async def test_filtro_por_tier(session, cadeia):
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(session, **(PADRAO | {"tier": 5}))
    assert {o.item for o in resposta.opportunities} == {"T5_PLANKS"}


async def test_filtro_por_familia(session, cadeia):
    await cadeia["semear"](PRECOS)
    resposta = await find_refining_opportunities(session, **(PADRAO | {"family": "planks"}))
    assert resposta.total == 4
    vazio = await find_refining_opportunities(session, **(PADRAO | {"family": "LEATHER"}))
    assert vazio.total == 0


async def test_spec_reduz_o_focus_e_sobe_a_prata_por_focus(session, cadeia):
    """A fase 16 ponta a ponta: o mesmo refino, com e sem especialização.

    O lucro em prata não muda — spec não mexe em preço nem em taxa —, mas o
    Focus gasto cai e prata/Focus sobe na mesma proporção. Como prata/Focus é a
    ordenação principal, é isso que muda a decisão.
    """
    await cadeia["semear"](PRECOS)

    sem = await find_refining_opportunities(
        session, **(PADRAO | {"sourcing": Sourcing.CRAFT})
    )
    com = await find_refining_opportunities(
        session,
        **(PADRAO | {"sourcing": Sourcing.CRAFT, "spec_levels": {"PLANKS": 100}}),
    )

    t5_sem = next(o for o in sem.opportunities if o.item == "T5_PLANKS")
    t5_com = next(o for o in com.opportunities if o.item == "T5_PLANKS")

    assert t5_sem.known and t5_com.known
    # 100 níveis × 250 pontos = 25.000 → 0,5^2,5 ≈ 17,68% do Focus original.
    assert t5_com.focus_per_unit < t5_sem.focus_per_unit * 0.2
    assert t5_com.profit == pytest.approx(t5_sem.profit)
    assert t5_com.profit_per_focus > t5_sem.profit_per_focus * 5


async def test_sem_spec_a_resposta_avisa_que_assumiu_zero(session, cadeia):
    """Custo do dump apresentado sem ressalva parece custo do usuário."""
    await cadeia["semear"](PRECOS)

    sem = await find_refining_opportunities(session, **PADRAO)
    assert sem.params.specialization.assumes_zero_spec is True
    assert sem.params.specialization.informed is False
    assert "PLANKS" in sem.params.specialization.families

    com = await find_refining_opportunities(
        session, **(PADRAO | {"spec_levels": {"PLANKS": 40}})
    )
    assert com.params.specialization.assumes_zero_spec is False
    assert com.params.specialization.levels["PLANKS"] == 40
