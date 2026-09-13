"""Score de oportunidade: pesos configuráveis, ausência não vira zero."""

from app.calculations.scoring import ScoreInputs, compute_score

PESOS = {
    "profit": 0.25, "margin": 0.20, "roi": 0.15,
    "freshness": 0.15, "liquidity": 0.15, "trend": 0.05,
    "distance": 0.03, "risk": 0.02,
}

COMPLETO = ScoreInputs(
    profit=500_000, margin_pct=20, roi_pct=25,
    freshness_seconds=0, liquidity_units_per_day=500, trend_pct=20,
)


def test_oportunidade_ideal_pontua_alto():
    resultado = compute_score(COMPLETO, PESOS)
    assert resultado.score >= 95
    assert resultado.band == "excelente"


def test_oportunidade_fraca_pontua_baixo():
    fraca = ScoreInputs(
        profit=1_000, margin_pct=1, roi_pct=1,
        freshness_seconds=21_600, liquidity_units_per_day=1, trend_pct=-20,
    )
    assert compute_score(fraca, PESOS).score < 20


def test_liquidez_desconhecida_nao_pontua_zero():
    """Punir por falta de dado trataria item novo como item ruim."""
    sem_liquidez = ScoreInputs(
        profit=500_000, margin_pct=20, roi_pct=25, freshness_seconds=0, trend_pct=20
    )
    resultado = compute_score(sem_liquidez, PESOS)
    assert resultado.score >= 95
    assert "liquidity" in resultado.missing


def test_confianca_cai_quando_falta_sinal():
    completo = compute_score(COMPLETO, PESOS)
    parcial = compute_score(ScoreInputs(profit=500_000, margin_pct=20), PESOS)
    assert completo.confidence > parcial.confidence
    assert parcial.confidence < 1.0


def test_score_nao_e_publicado_com_confianca_baixa():
    """Sem lucro nem margem, frescor e liquidez altos dariam 97 'excelente'.

    Um score alto ao lado de 'lucro desconhecido' é pior do que não ter score:
    dá confiança a uma oportunidade que ninguém avaliou.
    """
    so_contexto = ScoreInputs(freshness_seconds=0, liquidity_units_per_day=500)
    resultado = compute_score(so_contexto, PESOS)

    assert resultado.score is None
    assert resultado.band == "desconhecida"
    assert resultado.confidence < 0.5
    assert {"profit", "margin", "roi"} <= set(resultado.missing)


def test_limiar_de_confianca_e_ajustavel():
    so_contexto = ScoreInputs(freshness_seconds=0, liquidity_units_per_day=500)
    assert compute_score(so_contexto, PESOS, min_confidence=0.0).score is not None


def test_margem_enorme_com_liquidez_zero_perde_para_margem_menor_e_liquida():
    """Requisito 21: margem grande em item parado vale menos."""
    ilusoria = ScoreInputs(
        profit=500_000, margin_pct=60, roi_pct=60,
        freshness_seconds=0, liquidity_units_per_day=2, trend_pct=0,
    )
    solida = ScoreInputs(
        profit=200_000, margin_pct=12, roi_pct=15,
        freshness_seconds=0, liquidity_units_per_day=900, trend_pct=0,
    )
    pesos_liquidez = {**PESOS, "liquidity": 0.45, "profit": 0.1, "margin": 0.1, "roi": 0.1}
    assert (
        compute_score(solida, pesos_liquidez).score
        > compute_score(ilusoria, pesos_liquidez).score
    )


def test_preco_velho_derruba_o_score():
    fresco = compute_score(COMPLETO, PESOS).score
    velho = compute_score(
        ScoreInputs(
            profit=500_000, margin_pct=20, roi_pct=25,
            freshness_seconds=21_600, liquidity_units_per_day=500, trend_pct=20,
        ),
        PESOS,
    ).score
    assert velho < fresco


def test_pesos_sao_configuraveis():
    so_liquidez = {"liquidity": 1.0}
    resultado = compute_score(COMPLETO, so_liquidez)
    assert resultado.score == 100
    assert resultado.components["liquidity"] == 1.0


def test_sem_nenhum_sinal_o_score_e_none():
    resultado = compute_score(ScoreInputs(), PESOS)
    assert resultado.score is None
    assert resultado.confidence == 0.0


def test_tendencia_neutra_nao_penaliza():
    neutra = compute_score(
        ScoreInputs(profit=500_000, margin_pct=20, roi_pct=25,
                    freshness_seconds=0, liquidity_units_per_day=500, trend_pct=0),
        {"trend": 1.0},
    )
    assert neutra.score == 50
