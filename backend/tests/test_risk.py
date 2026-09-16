"""Risco de rota: a conta que separa a recomendação certa da que quebra.

O erro que estes testes existem para impedir: tratar a carga perdida como "lucro
zero". Perder a carga não é deixar de ganhar — é perder o que se investiu nela, e
essa diferença é o dobro do dano ou mais.
"""

import pytest

from app.calculations.risk import (
    DEFAULT_DISTANCE_FACTORS,
    RiskProfile,
    Zone,
    adjust_for_risk,
    classify_zone,
    distance_factor,
)

ABERTA = frozenset({"caerleon", "black-market"})


def test_cidade_real_para_cidade_real_e_azul():
    assert classify_zone("martlock", "lymhurst", ABERTA) is Zone.BLUE


def test_qualquer_ponta_em_caerleon_ou_black_market_atravessa_zona_aberta():
    assert classify_zone("martlock", "caerleon", ABERTA) is Zone.RED_BLACK
    assert classify_zone("caerleon", "martlock", ABERTA) is Zone.RED_BLACK
    assert classify_zone("lymhurst", "black-market", ABERTA) is Zone.RED_BLACK


def test_mesma_cidade_nao_e_rota():
    """Sem viagem não há emboscada. Não é otimismo: é a ausência do evento."""
    assert classify_zone("martlock", "martlock", ABERTA) is Zone.LOCAL
    assert RiskProfile(loss_pct_blue=0.5, loss_pct_red_black=0.9).probability(Zone.LOCAL) == 0.0


def test_perda_desconta_o_lucro_e_tambem_o_investimento():
    """A fórmula inteira: lucro × (1 − p) − investimento × p."""
    risco = adjust_for_risk(
        profit=10_000, investment=50_000, zone=Zone.RED_BLACK,
        profile=RiskProfile(loss_pct_red_black=0.2),
    )
    # 10.000 × 0,8 = 8.000; menos 50.000 × 0,2 = 10.000 → −2.000.
    assert risco.expected_profit == pytest.approx(-2000.0)
    assert risco.gross_profit == 10_000
    assert risco.expected_loss == pytest.approx(12_000.0)


def test_esquecer_o_investimento_subestimaria_o_dano():
    """Comparação explícita com a conta errada que quase todo mundo faz.

    Só `lucro × (1 − p)` daria 8.000 — positivo, "vale a pena". A conta certa dá
    −2.000. É a diferença entre recomendar e desaconselhar a mesma operação.
    """
    perfil = RiskProfile(loss_pct_red_black=0.2)
    certo = adjust_for_risk(10_000, 50_000, Zone.RED_BLACK, perfil).expected_profit
    errado = 10_000 * (1 - 0.2)

    assert errado > 0
    assert certo < 0
    assert errado - certo == pytest.approx(10_000.0)


def test_operacao_lucrativa_no_bruto_pode_nao_sobreviver_ao_risco():
    """É o caso que esta fase existe para tornar visível."""
    risco = adjust_for_risk(10_000, 50_000, Zone.RED_BLACK, RiskProfile(loss_pct_red_black=0.2))
    assert risco.gross_profit > 0
    assert risco.survives_risk is False


def test_risco_zero_deixa_o_ajustado_igual_ao_bruto():
    """Padrão zero não é chute: é "não estou modelando perda", e aparece."""
    perfil = RiskProfile()
    assert perfil.modelled is False
    risco = adjust_for_risk(10_000, 50_000, Zone.RED_BLACK, perfil)
    assert risco.expected_profit == risco.gross_profit == 10_000
    assert risco.expected_loss == 0


def test_cada_zona_usa_a_sua_probabilidade():
    perfil = RiskProfile(loss_pct_blue=0.01, loss_pct_red_black=0.25)
    azul = adjust_for_risk(1000, 1000, Zone.BLUE, perfil)
    vermelha = adjust_for_risk(1000, 1000, Zone.RED_BLACK, perfil)

    assert azul.loss_probability == 0.01
    assert vermelha.loss_probability == 0.25
    assert azul.expected_profit > vermelha.expected_profit


def test_sem_lucro_ou_investimento_o_ajustado_e_none_e_nao_zero():
    """Ausência de dado é None. Zero ali viraria "sem lucro", que é diferente."""
    risco = adjust_for_risk(None, 1000, Zone.BLUE, RiskProfile(loss_pct_blue=0.1))
    assert risco.expected_profit is None
    assert risco.known is False
    assert risco.loss_probability == 0.1


def test_probabilidade_fora_da_faixa_e_limitada():
    perfil = RiskProfile(loss_pct_red_black=1.7, loss_pct_blue=-0.3)
    assert perfil.probability(Zone.RED_BLACK) == 1.0
    assert perfil.probability(Zone.BLUE) == 0.0


def test_distancia_piora_conforme_a_zona():
    """Alimenta o componente `distance` do score, que existia sem fonte."""
    assert distance_factor(Zone.LOCAL) > distance_factor(Zone.BLUE)
    assert distance_factor(Zone.BLUE) > distance_factor(Zone.RED_BLACK)
    assert set(DEFAULT_DISTANCE_FACTORS) == set(Zone)


def test_fatores_de_distancia_sao_configuraveis():
    """São opinião do produto, não fato do jogo."""
    assert distance_factor(Zone.BLUE, {Zone.BLUE: 0.9}) == 0.9
