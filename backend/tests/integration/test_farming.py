"""Agricultura ponta a ponta: dump + preço de mercado + normalização por dia."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.farming import Farmable, FarmableOutput
from app.models.reference import DataSource, Location, Server
from app.repositories import market as market_repo
from app.services.farming_service import find_farming_plans

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)
CICLO = 79_200          # 22 h
CRESCIMENTO = 158_400   # 44 h

PADRAO = dict(
    server="west", buy_location="caerleon", sell_location="caerleon",
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    station=None, kind=None, tier=None, strategy=Strategy.FAST,
    sort_by="profit_per_day", limit=40,
)


@pytest.fixture
async def cenario(session):
    """Uma cenoura de 22 h e um boi de 44 h que come cenoura.

    É o formato mínimo que exercita a cadeia: o cultivo alimenta a criação.
    """
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)

    semente = Item(unique_name="T1_FARM_CARROT_SEED", base_name="T1_FARM_CARROT_SEED",
                   tier=1, enchantment=0, display_name_pt="Sementes de Cenoura",
                   subcategory_code="farm", is_tracked=True)
    cenoura = Item(unique_name="T1_CARROT", base_name="T1_CARROT", tier=1, enchantment=0,
                   display_name_pt="Cenouras", subcategory_code="farm",
                   nutrition=48, food_category="plants", is_tracked=True)
    minhoca = Item(unique_name="T1_WORM", base_name="T1_WORM", tier=1, enchantment=0,
                   display_name_pt="Minhoca", subcategory_code="fish", is_tracked=True)
    filhote = Item(unique_name="T3_FARM_OX_BABY", base_name="T3_FARM_OX_BABY", tier=3,
                   enchantment=0, display_name_pt="Bezerro", subcategory_code="pasture",
                   is_tracked=True)
    adulto = Item(unique_name="T3_FARM_OX_GROWN", base_name="T3_FARM_OX_GROWN", tier=3,
                  enchantment=0, display_name_pt="Boi", subcategory_code="pasture",
                  is_tracked=True)

    session.add_all([server, caerleon, source, semente, cenoura, minhoca, filhote, adulto])
    await session.flush()

    cultivo = Farmable(
        item_id=semente.id, station="farm", role="seed",
        cycle_seconds=CICLO, grow_seconds=CICLO, focus_cost=1000, max_cycles=1,
        npc_silver_cost=2000,
    )
    criacao = Farmable(
        item_id=filhote.id, station="pasture", role="baby",
        cycle_seconds=CICLO, grow_seconds=CRESCIMENTO, focus_cost=1000, max_cycles=1,
        grown_item_id=adulto.id, accepted_food_category="plants",
        seconds_per_nutrition=330.0, nutrition_max=480,
    )
    session.add_all([cultivo, criacao])
    await session.flush()

    session.add_all([
        FarmableOutput(farmable_id=cultivo.id, item_id=cenoura.id, role="harvest",
                       amount_min=3, amount_max=6, chance=1.0),
        FarmableOutput(farmable_id=cultivo.id, item_id=minhoca.id, role="harvest",
                       amount_min=1, amount_max=1, chance=0.1),
        FarmableOutput(farmable_id=cultivo.id, item_id=semente.id, role="seed_return",
                       amount_min=1, amount_max=1, chance=0.3333),
        FarmableOutput(farmable_id=criacao.id, item_id=adulto.id, role="grown",
                       amount_min=1, amount_max=1, chance=1.0),
        FarmableOutput(farmable_id=criacao.id, item_id=filhote.id, role="offspring",
                       amount_min=1, amount_max=1, chance=0.84),
    ])
    await session.flush()

    def preco(item, sell_min, buy_max, idade_minutos=5):
        quando = AGORA - timedelta(minutes=idade_minutos)
        return MarketPriceRecord(
            server_id=server.id, location_id=caerleon.id, item_id=item.id, quality=1,
            sell_price_min=sell_min, sell_price_min_date=quando,
            sell_price_max=sell_min, sell_price_max_date=quando,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=buy_max, buy_price_max_date=quando,
            observed_at=AGORA, source_id=source.id,
        )

    return {"semente": semente, "cenoura": cenoura, "minhoca": minhoca,
            "filhote": filhote, "adulto": adulto, "preco": preco}


async def semear(session, precos):
    await market_repo.upsert_prices(session, precos)
    await session.flush()


def plano(resposta, item):
    return next(p for p in resposta.plans if p.item == item)


async def test_cultivo_sai_normalizado_por_dia_e_por_focus(session, cenario):
    p = cenario["preco"]
    await semear(session, [
        p(cenario["semente"], 1000, 900),
        p(cenario["cenoura"], 600, 500),
        p(cenario["minhoca"], 100, 80),
    ])

    resposta = await find_farming_plans(session, **PADRAO)
    cultivo = plano(resposta, "T1_FARM_CARROT_SEED")
    eco = cultivo.economics

    assert cultivo.kind == "CULTIVO"
    assert cultivo.station_label == "fazenda"
    assert eco.known is True
    assert eco.cycle_seconds == CICLO
    # 22 horas: o lucro de um dia é maior que o de um ciclo.
    assert eco.profit_per_day > eco.profit_per_cycle
    assert eco.profit_per_focus == pytest.approx(eco.profit_per_cycle / 1000, abs=0.01)


async def test_criacao_custeia_a_racao_a_partir_do_cultivo(session, cenario):
    """Filhote → adulto consumindo cenoura: é a cadeia que o refino já resolvia."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["semente"], 1000, 900),
        p(cenario["cenoura"], 600, 500),
        p(cenario["minhoca"], 100, 80),
        p(cenario["filhote"], 20_000, 18_000),
        p(cenario["adulto"], 60_000, 55_000),
    ])

    resposta = await find_farming_plans(session, **PADRAO)
    criacao = plano(resposta, "T3_FARM_OX_BABY")

    assert criacao.kind == "CRIACAO"
    racao = next(i for i in criacao.inputs if i.role == "ração")
    assert racao.item == "T1_CARROT"
    # 158.400 s ÷ 330 s por ponto = 480 pontos; a 48 por cenoura, 10 cenouras.
    assert racao.quantity == pytest.approx(10.0, abs=0.001)
    assert racao.unit_price == 600
    assert criacao.economics.known is True
    assert criacao.economics.cycle_seconds == CRESCIMENTO


async def test_ciclo_longo_nao_ganha_do_curto_so_por_ser_longo(session, cenario):
    """O motivo de a ordenação padrão ser prata por dia."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["semente"], 1000, 900),
        p(cenario["cenoura"], 600, 500),
        p(cenario["minhoca"], 100, 80),
        p(cenario["filhote"], 20_000, 18_000),
        p(cenario["adulto"], 40_000, 36_000),
    ])

    resposta = await find_farming_plans(session, **PADRAO)
    cultivo = plano(resposta, "T1_FARM_CARROT_SEED").economics
    criacao = plano(resposta, "T3_FARM_OX_BABY").economics

    assert criacao.profit_per_cycle > cultivo.profit_per_cycle
    razao_ciclo = criacao.profit_per_cycle / cultivo.profit_per_cycle
    razao_dia = criacao.profit_per_day / cultivo.profit_per_day
    # O ciclo da criação é o dobro: por dia a vantagem encolhe pela metade.
    assert razao_dia == pytest.approx(razao_ciclo / 2, rel=0.01)


async def test_sem_racao_com_cotacao_a_criacao_fica_na_tela_com_o_motivo(session, cenario):
    """Sumir deixaria um buraco sem explicação."""
    p = cenario["preco"]
    await semear(session, [
        p(cenario["filhote"], 20_000, 18_000),
        p(cenario["adulto"], 60_000, 55_000),
    ])  # nenhuma cenoura cotada

    resposta = await find_farming_plans(session, **PADRAO)
    criacao = plano(resposta, "T3_FARM_OX_BABY")

    assert criacao.economics.known is False
    assert "ração" in criacao.economics.reason
    assert criacao.economics.profit_per_day is None


async def test_saida_incidental_nao_derruba_o_cultivo(session, cenario):
    """A minhoca cai a 10% e ninguém planta cenoura por causa dela.

    Regressão real: na primeira rodada com preço de verdade, todo cultivo virou
    UNKNOWN porque a minhoca da lista de loot não tem cotação. Chance 1.0 é o
    que separa o que o ciclo entrega sempre do que cai junto.
    """
    p = cenario["preco"]
    await semear(session, [
        p(cenario["semente"], 1000, 900),
        p(cenario["cenoura"], 600, 500),
    ])  # minhoca sem cotação

    resposta = await find_farming_plans(session, **PADRAO)
    cultivo = plano(resposta, "T1_FARM_CARROT_SEED")

    assert cultivo.economics.known is True
    assert cultivo.economics.outputs_without_price == ["T1_WORM"]
    assert [s.item for s in cultivo.outputs if s.primary] == ["T1_CARROT"]


async def test_semente_sem_cotacao_derruba_o_cultivo(session, cenario):
    p = cenario["preco"]
    await semear(session, [p(cenario["cenoura"], 600, 500)])

    resposta = await find_farming_plans(session, **PADRAO)
    cultivo = plano(resposta, "T1_FARM_CARROT_SEED")

    assert cultivo.economics.known is False
    assert "T1_FARM_CARROT_SEED" in cultivo.economics.reason


async def test_sem_taxas_o_lucro_e_unknown(session, cenario):
    p = cenario["preco"]
    await semear(session, [
        p(cenario["semente"], 1000, 900),
        p(cenario["cenoura"], 600, 500),
        p(cenario["minhoca"], 100, 80),
    ])

    resposta = await find_farming_plans(
        session, **(PADRAO | {"setup_fee_pct": None, "sales_tax_pct": None})
    )
    cultivo = plano(resposta, "T1_FARM_CARROT_SEED")

    assert resposta.params.complete is False
    assert cultivo.economics.known is False
    assert "taxas" in cultivo.economics.reason


async def test_adulto_sem_produto_nao_vira_plano(session, cenario):
    """Ele é saída de uma criação, não uma decisão própria."""
    p = cenario["preco"]
    await semear(session, [p(cenario["adulto"], 60_000, 55_000)])

    resposta = await find_farming_plans(session, **PADRAO)
    assert {plano.item for plano in resposta.plans} == {
        "T1_FARM_CARROT_SEED", "T3_FARM_OX_BABY"
    }


async def test_as_interpretacoes_vao_etiquetadas_na_resposta(session, cenario):
    """Número lido do dump e número interpretado não podem sair iguais."""
    resposta = await find_farming_plans(session, **PADRAO)

    assert resposta.params.assumptions
    assert any("activefarmmaxcycles" in linha for linha in resposta.params.assumptions)
    assert any("activefarmbonus" in linha for linha in resposta.params.assumptions)


async def test_filtro_por_estacao(session, cenario):
    resposta = await find_farming_plans(session, **(PADRAO | {"station": "pasture"}))
    assert {plano.station for plano in resposta.plans} == {"pasture"}
