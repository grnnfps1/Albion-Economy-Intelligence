"""Arbitragem ponta a ponta contra PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.fees import Strategy
from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.reference import DataSource, Location, Server
from app.models.settings import ConfigParameter
from app.repositories import market as market_repo
from app.services.arbitrage_service import find_arbitrage

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)


@pytest.fixture
async def cenario(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    lymhurst = Location(aodp_name="Lymhurst", slug="lymhurst",
                        display_name="Lymhurst", kind="royal_city")
    bm = Location(aodp_name="Black Market", slug="black-market",
                  display_name="Black Market", kind="black_market")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    couro = Item(unique_name="T5_LEATHER", base_name="T5_LEATHER", tier=5, enchantment=0,
                 display_name_pt="Couro Curtido", is_tracked=True)
    session.add_all([server, caerleon, lymhurst, bm, source, couro])
    await session.flush()

    def preco(local, sell_min, buy_max, idade_min=5):
        quando = AGORA - timedelta(minutes=idade_min)
        return MarketPriceRecord(
            server_id=server.id, location_id=local.id, item_id=couro.id, quality=2,
            sell_price_min=sell_min, sell_price_min_date=quando,
            sell_price_max=sell_min + 50 if sell_min else None,
            sell_price_max_date=quando if sell_min else None,
            buy_price_min=None, buy_price_min_date=None,
            buy_price_max=buy_max, buy_price_max_date=quando if buy_max else None,
            observed_at=AGORA, source_id=source.id,
        )

    return {"server": server, "caerleon": caerleon, "lymhurst": lymhurst, "bm": bm,
            "source": source, "item": couro, "preco": preco}


async def semear(session, cenario, precos):
    await market_repo.upsert_prices(session, precos)
    await session.flush()


async def test_sem_taxas_configuradas_o_lucro_e_unknown(session, cenario):
    """O produto diz 'não sei' em vez de um número calculado com taxa zero."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=None, sales_tax_pct=None, premium=None,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=False, min_profit=0, tracked_only=True, limit=50,
    )

    assert resposta.fees.complete is False
    assert resposta.fees.source == "UNKNOWN"
    assert resposta.total >= 1
    oportunidade = resposta.opportunities[0]
    assert oportunidade.economics.known is False
    assert "taxas não configuradas" in oportunidade.economics.reason
    assert oportunidade.economics.net_profit is None
    # O spread bruto continua visível — mas rotulado como bruto, não como lucro.
    assert oportunidade.spread_pct > 0


async def test_taxas_do_usuario_destravam_o_calculo(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=False, min_profit=0, tracked_only=True, limit=50,
    )

    assert resposta.fees.complete is True
    assert resposta.fees.source == "usuario"
    melhor = resposta.opportunities[0]
    assert melhor.economics.known is True
    assert melhor.origin == "Caerleon" and melhor.destination == "Lymhurst"
    assert melhor.economics.net_profit > 0
    assert melhor.score.value is not None


async def test_premium_muda_o_resultado(session, cenario):
    """Imposto depende da conta. Valor fixo mostraria lucro errado para metade."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    comum = dict(server="west", strategy=Strategy.FAST, quantity=100,
                 setup_fee_pct=0.025, premium=None, transport_cost_per_unit=0,
                 max_age_seconds=21600, include_black_market=False,
                 min_profit=0, tracked_only=True, limit=50)

    com_premium = await find_arbitrage(session, sales_tax_pct=0.04, **comum)
    sem_premium = await find_arbitrage(session, sales_tax_pct=0.08, **comum)

    assert (
        com_premium.opportunities[0].economics.net_profit
        > sem_premium.opportunities[0].economics.net_profit
    )


async def test_config_do_banco_e_usada_quando_o_usuario_nao_informa(session, cenario):
    session.add_all([
        ConfigParameter(key="market.sell_order_setup_fee_pct", value=0.025, source="teste"),
        ConfigParameter(key="market.sales_tax_pct.standard", value=0.08, source="teste"),
    ])
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=None, sales_tax_pct=None, premium=False,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=False, min_profit=0, tracked_only=True, limit=50,
    )

    assert resposta.fees.source == "config"
    assert resposta.fees.sales_tax_pct == 0.08


async def test_preco_velho_nao_vira_oportunidade(session, cenario):
    """Recomendar compra sobre cotação de ontem é recomendar às cegas."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100, idade_min=5),
                                    p(cenario["lymhurst"], 1800, 1650, idade_min=60 * 40)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=False, min_profit=0, tracked_only=True, limit=50,
    )
    assert resposta.total == 0


async def test_black_market_entra_como_destino_de_venda(session, cenario):
    """Validado em 16/09/2026: buy_price_max em 40/40, orientação normal.

    O que mudou em relação à suposição antiga: não há inversão de sinal. Vender
    no Black Market usa o mesmo campo que vender numa cidade.
    """
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["bm"], 3000, 2800)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
    )

    destinos = {op.destination_slug for op in resposta.opportunities}
    assert "black-market" in destinos


async def test_black_market_nunca_e_origem_de_compra(session, cenario):
    """Comprar lá não foi medido, e perna não medida não entra.

    O Black Market tem o preço mais barato do cenário; se a perna de compra
    estivesse aberta, ele apareceria como origem na hora.
    """
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["bm"], 100, 90),
                                    p(cenario["lymhurst"], 5000, 4800)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
    )

    assert all(op.origin_slug != "black-market" for op in resposta.opportunities)


async def test_black_market_pode_ser_desligado(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["bm"], 3000, 2800)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=False, min_profit=0, tracked_only=True, limit=50,
    )
    assert resposta.total == 0


async def test_rota_por_caerleon_e_classificada_como_zona_aberta(session, cenario):
    """A classificação é pelas pontas: o caminho é escolha do jogador."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
    )

    op = next(o for o in resposta.opportunities if o.origin_slug == "caerleon")
    assert op.risk.zone == "VERMELHA_PRETA"
    assert op.risk.crosses_open_world is True


async def test_risco_padrao_zero_deixa_ajustado_igual_ao_bruto(session, cenario):
    """Zero não é chute: é "não estou modelando perda", e aparece na resposta."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
    )

    assert resposta.risk.modelled is False
    assert resposta.risk.source == "padrao_zero"
    op = resposta.opportunities[0]
    assert op.risk.expected_profit == op.economics.net_profit
    assert op.risk.expected_loss == 0


async def test_risco_informado_desconta_lucro_e_investimento(session, cenario):
    """lucro x (1 - p) - investimento x p, com os dois números na resposta."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
        loss_pct_blue=0.0, loss_pct_red_black=0.25,
    )

    assert resposta.risk.modelled is True
    assert resposta.risk.source == "usuario"

    vermelha = next(o for o in resposta.opportunities if o.risk.crosses_open_world)
    eco, risco = vermelha.economics, vermelha.risk
    esperado = eco.net_profit * 0.75 - eco.investment * 0.25

    assert risco.loss_probability == 0.25
    assert risco.expected_profit == pytest.approx(esperado, abs=0.01)
    # Os dois números lado a lado: o bruto continua visível.
    assert risco.gross_profit == eco.net_profit


async def test_zona_azul_e_menos_descontada_que_a_vermelha(session, cenario):
    """Rota de zona vermelha paga mais porque pode custar a carga inteira."""
    p = cenario["preco"]
    martlock = Location(aodp_name="Martlock", slug="martlock",
                        display_name="Martlock", kind="royal_city")
    session.add(martlock)
    await session.flush()

    await semear(session, cenario, [
        p(cenario["lymhurst"], 1200, 1100),
        p(martlock, 1800, 1650),
        p(cenario["caerleon"], 1800, 1650),
    ])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
        loss_pct_blue=0.01, loss_pct_red_black=0.30,
    )

    azul = next(o for o in resposta.opportunities
                if o.origin_slug == "lymhurst" and o.destination_slug == "martlock")
    vermelha = next(o for o in resposta.opportunities
                    if o.origin_slug == "lymhurst" and o.destination_slug == "caerleon")

    # Mesmo lucro bruto, porque os preços são os mesmos.
    assert azul.economics.net_profit == vermelha.economics.net_profit
    # E resultados muito diferentes depois do risco.
    assert azul.risk.expected_profit > vermelha.risk.expected_profit


async def test_score_usa_os_pesos_de_risco_e_distancia(session, cenario):
    """Os dois estavam em config_parameters desde a fase 0 e nunca eram usados."""
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1800, 1650)])

    resposta = await find_arbitrage(
        session, server="west", strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
        transport_cost_per_unit=0, max_age_seconds=21600,
        include_black_market=True, min_profit=0, tracked_only=True, limit=50,
        loss_pct_blue=0.02, loss_pct_red_black=0.30,
    )

    op = resposta.opportunities[0]
    assert "risk" in op.score.components
    assert "distance" in op.score.components
    assert "risk" not in op.score.missing
    assert "distance" not in op.score.missing


async def test_transporte_pode_inverter_o_sinal(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1100),
                                    p(cenario["lymhurst"], 1400, 1300)])

    comum = dict(server="west", strategy=Strategy.FAST, quantity=100,
                 setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
                 max_age_seconds=21600, include_black_market=False,
                 min_profit=0, tracked_only=True, limit=50)

    sem = await find_arbitrage(session, transport_cost_per_unit=0, **comum)
    com = await find_arbitrage(session, transport_cost_per_unit=400, **comum)

    assert sem.total >= 1
    # Com transporte caro, nada sobrevive ao filtro de lucro mínimo.
    assert com.total == 0


async def test_estrategia_paciente_rende_menos_que_imediata_no_mesmo_spread(session, cenario):
    p = cenario["preco"]
    await semear(session, cenario, [p(cenario["caerleon"], 1200, 1150),
                                    p(cenario["lymhurst"], 1800, 1700)])

    comum = dict(quantity=100, setup_fee_pct=0.025, sales_tax_pct=0.04,
                 premium=True, transport_cost_per_unit=0, max_age_seconds=21600,
                 include_black_market=False, min_profit=0, tracked_only=True, limit=50)

    imediata = await find_arbitrage(session, server="west", strategy=Strategy.FAST, **comum)
    paciente = await find_arbitrage(session, server="west", strategy=Strategy.PATIENT, **comum)

    assert imediata.opportunities[0].economics.known
    assert paciente.opportunities[0].economics.known
    # A paciente compra e vende a preços melhores, mas paga setup fee duas vezes.
    assert paciente.opportunities[0].economics.fees > imediata.opportunities[0].economics.fees
