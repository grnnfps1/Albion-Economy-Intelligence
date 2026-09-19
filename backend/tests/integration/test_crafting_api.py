"""Crafting ponta a ponta: receita do dump + preço de mercado + cálculo."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.crafting_service import find_crafting_opportunities

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)

PADRAO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    return_rate=0.15, station_fee_per_100_nutrition=1000,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    crafts=1, strategy=Strategy.FAST, sort_by="profit_per_focus",
    tier=None, station_category=None, limit=30,
)


@pytest.fixture
async def cenario(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)

    # `item_value` espelha o dump real: dobra a cada tier. É o que determina a
    # nutrição consumida e, portanto, a taxa da estação.
    planks = Item(unique_name="T4_PLANKS", base_name="T4_PLANKS", tier=4, enchantment=0,
                  display_name_pt="Tábuas de Pinho", subcategory_code="refinedresources",
                  item_value=16, is_tracked=True)
    wood = Item(unique_name="T4_WOOD", base_name="T4_WOOD", tier=4, enchantment=0,
                display_name_pt="Madeira", subcategory_code="resources",
                item_value=4, is_tracked=True)
    t3 = Item(unique_name="T3_PLANKS", base_name="T3_PLANKS", tier=3, enchantment=0,
              display_name_pt="Tábuas T3", subcategory_code="refinedresources",
              item_value=8, is_tracked=True)
    token = Item(unique_name="T1_FACTION_TOKEN", base_name="T1_FACTION_TOKEN", tier=1,
                 enchantment=0, display_name_pt="Token", subcategory_code="cityresources",
                 is_tracked=True)
    session.add_all([server, caerleon, source, planks, wood, t3, token])
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

    def preco(item, sell_min, buy_max):
        quando = AGORA - timedelta(minutes=5)
        return MarketPriceRecord(
            server_id=server.id, location_id=caerleon.id, item_id=item.id, quality=1,
            sell_price_min=sell_min, sell_price_min_date=quando,
            sell_price_max=sell_min, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=buy_max, buy_price_max_date=quando,
            observed_at=AGORA, source_id=source.id,
        )

    return {"planks": planks, "wood": wood, "t3": t3, "token": token,
            "receita": receita, "preco": preco, "server": server,
            "caerleon": caerleon, "source": source}


async def semear(session, cenario, precos):
    await market_repo.upsert_prices(session, precos)
    await session.flush()


async def test_craft_lucrativo(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    resposta = await find_crafting_opportunities(session, **PADRAO)

    assert resposta.total == 1
    op = resposta.opportunities[0]
    assert op.item == "T4_PLANKS"
    assert op.economics.known is True
    assert op.economics.profit > 0
    assert op.economics.focus_cost == 54
    assert op.economics.profit_per_focus == pytest.approx(op.economics.profit / 54, abs=0.01)
    assert len(op.materials) == 2
    assert {m.item for m in op.materials} == {"T4_WOOD", "T3_PLANKS"}


async def test_sem_parametros_o_lucro_e_unknown(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"return_rate": None, "station_fee_per_100_nutrition": None,
                              "setup_fee_pct": None, "sales_tax_pct": None})
    )

    assert resposta.params.complete is False
    assert "crafting.return_rate" in resposta.params.missing
    assert "crafting.station_fee_per_100_nutrition" in resposta.params.missing
    op = resposta.opportunities[0]
    assert op.economics.known is False
    assert op.economics.profit is None


async def test_material_sem_cotacao_derruba_o_craft(session, cenario):
    """Custo parcial não é custo menor — é custo desconhecido."""
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["planks"], 5000, 4500),
    ])  # T3_PLANKS sem preço

    resposta = await find_crafting_opportunities(session, **PADRAO)
    op = resposta.opportunities[0]

    assert op.economics.known is False
    assert "T3_PLANKS" in op.economics.reason
    assert op.economics.profit is None


async def test_retorno_maior_aumenta_o_lucro(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    baixo = await find_crafting_opportunities(session, **(PADRAO | {"return_rate": 0.0}))
    alto = await find_crafting_opportunities(session, **(PADRAO | {"return_rate": 0.5}))

    assert alto.opportunities[0].economics.profit > baixo.opportunities[0].economics.profit
    assert alto.opportunities[0].economics.returned_value > 0


async def test_premium_muda_o_lucro(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    com = await find_crafting_opportunities(session, **(PADRAO | {"sales_tax_pct": 0.04}))
    sem = await find_crafting_opportunities(session, **(PADRAO | {"sales_tax_pct": 0.08}))

    assert com.opportunities[0].economics.profit > sem.opportunities[0].economics.profit


async def test_varias_execucoes_escalam_focus_e_lucro(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    uma = await find_crafting_opportunities(session, **PADRAO)
    dez = await find_crafting_opportunities(session, **(PADRAO | {"crafts": 10}))

    assert dez.opportunities[0].economics.focus_cost == 540
    assert dez.opportunities[0].economics.profit == pytest.approx(
        uma.opportunities[0].economics.profit * 10, abs=1
    )
    # Prata por focus não muda com a escala: é intensivo, não extensivo.
    assert dez.opportunities[0].economics.profit_per_focus == pytest.approx(
        uma.opportunities[0].economics.profit_per_focus, abs=0.01
    )


async def test_craft_com_prejuizo_aparece_mas_com_lucro_negativo(session, cenario):
    """Esconder o prejuízo faria o usuário achar que a receita não existe."""
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 3000, 2900),
        p(cenario["t3"], 3000, 2900),
        p(cenario["planks"], 4000, 3500),
    ])

    resposta = await find_crafting_opportunities(session, **PADRAO)
    assert resposta.opportunities[0].economics.profit < 0


async def test_parametros_usados_vao_na_resposta(session, cenario):
    """Sem isso, um lucro de 18% não é auditável."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["wood"], 1000, 900),
                                    p(cenario["t3"], 800, 700),
                                    p(cenario["planks"], 5000, 4500)])

    resposta = await find_crafting_opportunities(session, **PADRAO)

    assert resposta.params.return_rate == 0.15
    assert resposta.params.station_fee_per_100_nutrition == 1000
    assert resposta.params.nutrition_per_item_value == 0.1125
    assert resposta.params.fees.sales_tax_pct == 0.04
    assert resposta.params.fees.premium is True
    assert resposta.params.complete is True


async def test_rota_dentro_da_mesma_cidade_nao_tem_risco(session, cenario):
    """Sem viagem não há emboscada, mesmo com risco informado."""
    p = cenario["preco"]
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        p(cenario["planks"], 5000, 4500),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"loss_pct_blue": 0.1, "loss_pct_red_black": 0.5})
    )
    op = resposta.opportunities[0]

    assert op.risk.zone == "MESMA_CIDADE"
    assert op.risk.loss_probability == 0.0
    assert op.risk.expected_profit == op.economics.profit


async def test_vender_em_outra_cidade_desconta_o_risco(session, cenario):
    """Os dois números lado a lado: o bruto e o ajustado.

    Comprando em Caerleon, *qualquer* venda fora dela atravessa zona aberta —
    a classificação é pelas pontas, e uma delas já é Caerleon.
    """
    p = cenario["preco"]
    lymhurst = Location(aodp_name="Lymhurst", slug="lymhurst",
                        display_name="Lymhurst", kind="royal_city")
    session.add(lymhurst)
    await session.flush()

    quando = AGORA - timedelta(minutes=5)
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        MarketPriceRecord(
            server_id=cenario["server"].id, location_id=lymhurst.id,
            item_id=cenario["planks"].id, quality=1,
            sell_price_min=5000, sell_price_min_date=quando,
            sell_price_max=5000, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=4500, buy_price_max_date=quando,
            observed_at=AGORA, source_id=cenario["source"].id,
        ),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sell_location": "lymhurst", "loss_pct_red_black": 0.1})
    )
    op = resposta.opportunities[0]

    assert op.risk.zone == "VERMELHA_PRETA"
    assert op.risk.loss_probability == 0.1
    assert op.risk.gross_profit == op.economics.profit
    assert op.risk.expected_profit < op.risk.gross_profit
    # O desconto inclui o capital: não é só lucro x 0,9.
    assert op.risk.expected_profit < op.economics.profit * 0.9


async def test_vender_no_black_market_atravessa_zona_aberta(session, cenario):
    """O destino validado em 16/09/2026 — e ele não é de graça."""
    p = cenario["preco"]
    bm = Location(aodp_name="Black Market", slug="black-market",
                  display_name="Black Market", kind="black_market")
    session.add(bm)
    await session.flush()

    quando = AGORA - timedelta(minutes=5)
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        MarketPriceRecord(
            server_id=cenario["server"].id, location_id=bm.id,
            item_id=cenario["planks"].id, quality=1,
            sell_price_min=7000, sell_price_min_date=quando,
            sell_price_max=7000, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=6500, buy_price_max_date=quando,
            observed_at=AGORA, source_id=cenario["source"].id,
        ),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sell_location": "black-market", "loss_pct_red_black": 0.3})
    )
    op = resposta.opportunities[0]

    assert op.risk.zone == "VERMELHA_PRETA"
    assert op.risk.crosses_open_world is True
    assert op.risk.loss_probability == 0.3
    assert op.economics.known is True


async def test_risco_alto_pode_derrubar_um_craft_lucrativo(session, cenario):
    """Lucrativo no bruto, negativo no ajustado. É o caso que a tela precisa mostrar."""
    p = cenario["preco"]
    bm = Location(aodp_name="Black Market", slug="black-market",
                  display_name="Black Market", kind="black_market")
    session.add(bm)
    await session.flush()

    quando = AGORA - timedelta(minutes=5)
    await semear(session, cenario, [
        p(cenario["wood"], 1000, 900),
        p(cenario["t3"], 800, 700),
        MarketPriceRecord(
            server_id=cenario["server"].id, location_id=bm.id,
            item_id=cenario["planks"].id, quality=1,
            sell_price_min=3200, sell_price_min_date=quando,
            sell_price_max=3200, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=3100, buy_price_max_date=quando,
            observed_at=AGORA, source_id=cenario["source"].id,
        ),
    ])

    resposta = await find_crafting_opportunities(
        session, **(PADRAO | {"sell_location": "black-market", "loss_pct_red_black": 0.35})
    )
    op = resposta.opportunities[0]

    assert op.risk.gross_profit > 0
    assert op.risk.survives_risk is False
    assert op.risk.expected_profit < 0
