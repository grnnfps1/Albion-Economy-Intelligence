"""Onde comprar cada material, quando o preço varia de cidade para cidade.

A pergunta que estes testes cercam: quando vale espalhar a compra por várias
cidades, e quando espalhar é só ilusão de economia.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.crafting_service import find_crafting_opportunities
from app.services.refining_service import find_refining_opportunities
from app.services.sourcing import SourcingMode

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)
UMA_HORA = 3600

PADRAO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    return_rate=0.15, station_fee=100,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    crafts=1, strategy=Strategy.FAST, sort_by="profit_per_focus",
    tier=None, station_category=None, limit=30,
    max_age_seconds=UMA_HORA,
)

REFINO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    sourcing=Sourcing.CRAFT, return_rate=0.15, station_fee=100,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    family=None, tier=None, strategy=Strategy.FAST, limit=30,
    max_age_seconds=UMA_HORA,
)


@pytest.fixture
async def cenario(session):
    """T4_PLANKS = 2× T4_WOOD + 1× T3_PLANKS, com três cidades e o Black Market."""
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    cidades = {
        "caerleon": Location(aodp_name="Caerleon", slug="caerleon",
                             display_name="Caerleon", kind="royal_city"),
        "lymhurst": Location(aodp_name="Lymhurst", slug="lymhurst",
                             display_name="Lymhurst", kind="royal_city"),
        "martlock": Location(aodp_name="Martlock", slug="martlock",
                             display_name="Martlock", kind="royal_city"),
        # Semântica de ordens invertida e não validada: não pode virar perna de
        # compra por ser o mais barato da lista.
        "black": Location(aodp_name="Black Market", slug="black-market",
                          display_name="Black Market", kind="black_market"),
    }
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)

    planks = Item(unique_name="T4_PLANKS", base_name="T4_PLANKS", tier=4, enchantment=0,
                  display_name_pt="Tábuas de Pinho", subcategory_code="refinedresources",
                  is_tracked=True)
    wood = Item(unique_name="T4_WOOD", base_name="T4_WOOD", tier=4, enchantment=0,
                display_name_pt="Madeira", subcategory_code="resources", is_tracked=True)
    t3 = Item(unique_name="T3_PLANKS", base_name="T3_PLANKS", tier=3, enchantment=0,
              display_name_pt="Tábuas T3", subcategory_code="refinedresources", is_tracked=True)

    session.add_all([server, source, *cidades.values(), planks, wood, t3])
    await session.flush()

    receita = Recipe(output_item_id=planks.id, variant_index=0, output_quantity=1,
                     focus_cost=54, silver_cost=0, station_category="wood")
    session.add(receita)
    await session.flush()
    session.add_all([
        RecipeMaterial(recipe_id=receita.id, item_id=wood.id, quantity=2, is_returnable=True),
        RecipeMaterial(recipe_id=receita.id, item_id=t3.id, quantity=1, is_returnable=True),
    ])
    await session.flush()

    def preco(item, cidade, sell_min, buy_max=None, idade_minutos=5):
        quando = AGORA - timedelta(minutes=idade_minutos)
        return MarketPriceRecord(
            server_id=server.id, location_id=cidades[cidade].id, item_id=item.id, quality=1,
            sell_price_min=sell_min, sell_price_min_date=quando,
            sell_price_max=sell_min, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=buy_max, buy_price_max_date=quando,
            observed_at=AGORA, source_id=source.id,
        )

    return {"planks": planks, "wood": wood, "t3": t3, "preco": preco, "cidades": cidades}


async def semear(session, precos):
    await market_repo.upsert_prices(session, precos)
    await session.flush()


def material(op, nome):
    return next(m for m in op.materials if m.item == nome)


async def test_escolhe_o_menor_preco_de_cada_material(session, cenario):
    """Cada material na cidade mais barata, não todos na mesma."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "lymhurst", 700),          # madeira mais barata aqui
        p(cenario["t3"], "caerleon", 800),
        p(cenario["t3"], "martlock", 500),            # tábua T3 mais barata aqui
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert material(op, "T4_WOOD").location == "Lymhurst"
    assert material(op, "T3_PLANKS").location == "Martlock"
    # 2 unidades de madeira a 300 a menos + 1 tábua a 300 a menos.
    assert material(op, "T4_WOOD").savings_vs_base == 600
    assert material(op, "T3_PLANKS").savings_vs_base == 300
    assert all(m.is_alternate_city for m in op.materials)

    assert op.material_sourcing.cities_involved == 2
    assert op.material_sourcing.cities == ["Lymhurst", "Martlock"]
    assert op.material_sourcing.savings > 0


async def test_empate_fica_na_cidade_base(session, cenario):
    """Segunda cidade só se paga quando economiza; empate com viagem é prejuízo."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "lymhurst", 1000),         # exatamente o mesmo preço
        p(cenario["t3"], "caerleon", 800),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert material(op, "T4_WOOD").location == "Caerleon"
    assert material(op, "T4_WOOD").is_alternate_city is False
    assert op.material_sourcing.cities_involved == 1
    assert op.material_sourcing.savings == 0


async def test_preco_velho_nao_entra_na_escolha(session, cenario):
    """Comprar barato num preço de ontem é pior que comprar caro num de agora."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        # Metade do preço, mas de três dias atrás: a ordem já não existe.
        p(cenario["wood"], "lymhurst", 500, idade_minutos=3 * 24 * 60),
        p(cenario["t3"], "caerleon", 800),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert material(op, "T4_WOOD").location == "Caerleon"
    assert material(op, "T4_WOOD").unit_price == 1000
    assert op.material_sourcing.cities_involved == 1


async def test_cidade_unica_vence_quando_a_dispersao_nao_compensa(session, cenario):
    """A base já é a mais barata: espalhar não teria o que economizar."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 700),
        p(cenario["wood"], "lymhurst", 1200),
        p(cenario["t3"], "caerleon", 500),
        p(cenario["t3"], "martlock", 900),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    unica = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.SINGLE_CITY})
    )
    barato = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )

    assert {m.location for m in barato.opportunities[0].materials} == {"Caerleon"}
    assert barato.opportunities[0].material_sourcing.cities_involved == 1
    assert barato.opportunities[0].material_sourcing.savings == 0
    assert (
        barato.opportunities[0].economics.profit == unica.opportunities[0].economics.profit
    )


async def test_nao_desvia_para_cidade_mais_cara_quando_a_base_esta_velha(session, cenario):
    """MAIS_BARATO não pode piorar o custo.

    A cotação da base está velha e a única fresca de fora é mais cara. Trocar
    de cidade encareceria a compra para ganhar frescor -- e a pessoa pediu preço
    menor, não preço mais novo.
    """
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 700, idade_minutos=3 * 24 * 60),
        p(cenario["wood"], "lymhurst", 1200),
        p(cenario["t3"], "caerleon", 500),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert material(op, "T4_WOOD").location == "Caerleon"
    assert material(op, "T4_WOOD").unit_price == 700


async def test_black_market_nao_vira_perna_de_compra(session, cenario):
    """Ele não é cidade e a semântica de ordens é invertida."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "black", 10),              # barato demais para ser verdade
        p(cenario["t3"], "caerleon", 800),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert material(op, "T4_WOOD").location == "Caerleon"
    assert "Black Market" not in op.material_sourcing.cities


async def test_material_sem_cotacao_em_lugar_nenhum_derruba_o_craft(session, cenario):
    """Custo parcial não é custo menor -- nem varrendo sete cidades."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "lymhurst", 700),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])  # T3_PLANKS sem cotação em cidade nenhuma

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )
    op = resposta.opportunities[0]

    assert op.economics.known is False
    assert "T3_PLANKS" in op.economics.reason


async def test_comparar_devolve_os_dois_roteiros_e_a_diferenca(session, cenario):
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "lymhurst", 700),
        p(cenario["t3"], "caerleon", 800),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sourcing_mode": SourcingMode.COMPARE})
    )
    roteiro = resposta.opportunities[0].material_sourcing

    assert resposta.sourcing_mode == "COMPARAR"
    assert roteiro.cost_single_city > roteiro.cost_cheapest
    assert roteiro.savings == pytest.approx(
        roteiro.cost_single_city - roteiro.cost_cheapest, abs=0.01
    )
    assert roteiro.savings_pct > 0
    # Os dois roteiros levados até o lucro, não só até o custo.
    assert roteiro.profit_cheapest > roteiro.profit_single_city


async def test_cidade_unica_e_o_padrao(session, cenario):
    """Quem não pede espalhamento continua comprando tudo na cidade base."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["wood"], "lymhurst", 700),
        p(cenario["t3"], "caerleon", 800),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    resposta = await find_crafting_opportunities(session, **PADRAO)
    op = resposta.opportunities[0]

    assert resposta.sourcing_mode == "CIDADE_UNICA"
    assert material(op, "T4_WOOD").location == "Caerleon"
    assert material(op, "T4_WOOD").unit_price == 1000
    assert op.material_sourcing.cities_involved == 1


async def test_refino_tambem_escolhe_a_cidade_de_cada_elo(session, cenario):
    """A cadeia consulta a política de cidade sem saber que cidades existem."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["wood"], "caerleon", 1000),
        p(cenario["t3"], "caerleon", 900),
        p(cenario["t3"], "martlock", 400),
        p(cenario["planks"], "caerleon", 5000, buy_max=4500),
    ])

    unica = await find_refining_opportunities(
        session, **(REFINO | {"sourcing_mode": SourcingMode.SINGLE_CITY})
    )
    barato = await find_refining_opportunities(
        session, **(REFINO | {"sourcing_mode": SourcingMode.CHEAPEST})
    )

    alvo = next(op for op in barato.opportunities if op.item == "T4_PLANKS")
    elo = next(passo for passo in alvo.chain if passo.item == "T3_PLANKS")

    assert elo.location == "Martlock"
    assert elo.savings_vs_base == 500
    assert alvo.material_sourcing.savings > 0
    # Madeira em Caerleon, tábua T3 em Martlock.
    assert alvo.material_sourcing.cities_involved == 2

    antes = next(op for op in unica.opportunities if op.item == "T4_PLANKS")
    assert alvo.unit_cost < antes.unit_cost
