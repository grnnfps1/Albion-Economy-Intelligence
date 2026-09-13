"""Ranking de Focus: a taxa cruzada com os dois tetos."""

import pytest

from app.calculations.focus import (
    FocusCandidate,
    Limiter,
    Route,
    build_ranking,
    plan_for,
)


def candidato(item="T5_PLANKS", lucro=100.0, focus=10.0, giro=500.0, rota=Route.CRAFT):
    return FocusCandidate(item, rota, lucro, focus, giro)


class TestPlano:
    def test_taxa_e_ganho_sao_coisas_diferentes(self):
        plano = plan_for(candidato(), focus_budget=1000, horizon_days=7)
        assert plano.profit_per_focus == 10.0        # taxa
        assert plano.realizable_profit == 10_000.0   # ganho no horizonte

    def test_focus_limita_quando_o_mercado_escoa(self):
        plano = plan_for(candidato(giro=10_000), focus_budget=1000, horizon_days=7)
        assert plano.limiter is Limiter.FOCUS
        assert plano.units == 100.0

    def test_liquidez_limita_quando_o_item_nao_gira(self):
        """Prata/focus alta em item parado é armadilha."""
        plano = plan_for(candidato(giro=3), focus_budget=100_000, horizon_days=7)
        assert plano.limiter is Limiter.LIQUIDITY
        assert plano.units == 21.0
        assert plano.days_to_sell == 7.0

    def test_liquidez_desconhecida_nao_vira_infinita(self):
        plano = plan_for(candidato(giro=None), focus_budget=1000, horizon_days=7)
        assert plano.limiter is Limiter.UNKNOWN
        # O teto de Focus ainda é aplicado; o que não se sabe é se o mercado
        # aguenta.
        assert plano.units == 100.0

    def test_sem_orcamento_de_focus_o_teto_e_so_o_mercado(self):
        plano = plan_for(candidato(giro=50), focus_budget=None, horizon_days=7)
        assert plano.limiter is Limiter.LIQUIDITY
        assert plano.units == 350.0

    def test_sem_focus_na_receita_nao_ha_taxa(self):
        plano = plan_for(candidato(focus=0), focus_budget=1000, horizon_days=7)
        assert plano.profit_per_focus is None

    def test_horizonte_maior_aumenta_o_que_da_para_escoar(self):
        curto = plan_for(candidato(giro=10), focus_budget=1e9, horizon_days=1)
        longo = plan_for(candidato(giro=10), focus_budget=1e9, horizon_days=30)
        assert longo.units > curto.units


class TestRanking:
    def test_taxa_alta_em_item_parado_perde_para_taxa_menor_e_liquida(self):
        """É a razão de o ranking existir: prata/focus sozinha engana."""
        parado = candidato("T8_RARO", lucro=5_000, focus=100, giro=1)
        liquido = candidato("T5_COMUM", lucro=200, focus=10, giro=800)

        ranking = build_ranking([parado, liquido], focus_budget=50_000, horizon_days=7)

        assert ranking[0].item == "T5_COMUM"
        # A taxa do item parado é maior; o ganho realizável é menor.
        por_item = {p.item: p for p in ranking}
        assert por_item["T8_RARO"].profit_per_focus > por_item["T5_COMUM"].profit_per_focus
        assert por_item["T8_RARO"].realizable_profit < por_item["T5_COMUM"].realizable_profit

    def test_ordenar_por_taxa_inverte_o_resultado(self):
        parado = candidato("T8_RARO", lucro=5_000, focus=100, giro=1)
        liquido = candidato("T5_COMUM", lucro=200, focus=10, giro=800)

        ranking = build_ranking(
            [parado, liquido], focus_budget=50_000, horizon_days=7, sort_by="profit_per_focus"
        )
        assert ranking[0].item == "T8_RARO"

    def test_item_por_duas_rotas_fica_com_a_melhor(self):
        craft = candidato("T5_PLANKS", lucro=100, rota=Route.CRAFT)
        refino = candidato("T5_PLANKS", lucro=300, rota=Route.REFINE)

        ranking = build_ranking([craft, refino], focus_budget=1000, horizon_days=7)

        assert len(ranking) == 1
        assert ranking[0].route is Route.REFINE

    def test_lista_vazia(self):
        assert build_ranking([], focus_budget=1000) == []

    def test_operacao_sem_dado_fica_no_fim(self):
        completo = candidato("T5_OK", lucro=100, giro=500)
        incompleto = FocusCandidate("T5_SEM", Route.CRAFT, 100.0, 0.0, None)

        ranking = build_ranking([completo, incompleto], focus_budget=None, horizon_days=7)
        assert ranking[-1].item == "T5_SEM"

    def test_focus_usado_nunca_passa_do_orcamento(self):
        candidatos = [candidato(f"T{i}", giro=10_000) for i in range(4, 8)]
        for plano in build_ranking(candidatos, focus_budget=1000, horizon_days=7):
            assert plano.focus_used <= 1000 + 1e-6


def test_dias_para_escoar_e_visivel():
    """O número que responde 'quanto tempo meu capital fica preso'."""
    plano = plan_for(candidato(giro=20), focus_budget=1e9, horizon_days=30)
    assert plano.days_to_sell == pytest.approx(30.0)
