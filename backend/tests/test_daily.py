"""Lucro por dia em craft e refino: o que torna a fazenda comparável."""

import pytest

from app.calculations.daily import DailyLimiter, daily_yield


class TestLimitador:
    def test_focus_limita_quando_o_mercado_e_largo(self):
        r = daily_yield(unit_profit=100, focus_per_unit=50, focus_per_day=10_000,
                        market_units_per_day=5_000)
        assert r.units == 200            # 10.000 / 50
        assert r.limiter is DailyLimiter.FOCUS
        assert r.profit == pytest.approx(20_000)

    def test_mercado_limita_quando_o_focus_sobra(self):
        r = daily_yield(unit_profit=100, focus_per_unit=1, focus_per_day=10_000,
                        market_units_per_day=30)
        assert r.units == 30
        assert r.limiter is DailyLimiter.MERCADO if hasattr(DailyLimiter, "MERCADO") \
            else r.limiter is DailyLimiter.MARKET
        assert r.profit == pytest.approx(3_000)

    def test_empate_conta_como_mercado(self):
        """O teto que não se muda subindo spec é o que manda a decisão."""
        r = daily_yield(unit_profit=10, focus_per_unit=10, focus_per_day=1_000,
                        market_units_per_day=100)
        assert r.units == 100
        assert r.limiter is DailyLimiter.MARKET

    def test_os_dois_tetos_vao_na_resposta(self):
        """Saber qual é a trava exige ver os dois números."""
        r = daily_yield(unit_profit=1, focus_per_unit=50, focus_per_day=10_000,
                        market_units_per_day=30)
        assert r.units_by_focus == 200
        assert r.units_by_market == 30


class TestSemFocus:
    def test_operacao_sem_focus_e_limitada_so_pelo_mercado(self):
        r = daily_yield(unit_profit=7, focus_per_unit=0, focus_per_day=10_000,
                        market_units_per_day=40)
        assert r.units == 40
        assert r.limiter is DailyLimiter.MARKET
        assert r.units_by_focus is None

    def test_sem_focus_e_sem_giro_e_unknown_e_nao_zero(self):
        """Sem teto nenhum, "por dia" não tem resposta.

        Devolver o lucro unitário como se fosse diário erraria por um fator
        arbitrário — que é exatamente o que a regra 12 proíbe.
        """
        r = daily_yield(unit_profit=7, focus_per_unit=0, focus_per_day=10_000,
                        market_units_per_day=None)
        assert r.known is False
        assert r.profit is None
        assert "nada limita o dia" in r.reason


class TestUnknown:
    def test_sem_lucro_unitario_e_unknown(self):
        assert daily_yield(None, 10, 10_000, 100).known is False

    def test_operacao_com_focus_sem_orcamento_e_unknown(self):
        r = daily_yield(unit_profit=10, focus_per_unit=5, focus_per_day=None,
                        market_units_per_day=100)
        assert r.known is False
        assert "Focus" in r.reason

    def test_giro_zero_nao_e_teto_e_sim_ausencia(self):
        """Giro 0 vindo da liquidez é "não medido", não "mercado fechado"."""
        r = daily_yield(unit_profit=10, focus_per_unit=5, focus_per_day=10_000,
                        market_units_per_day=0)
        assert r.limiter is DailyLimiter.FOCUS
        assert r.units == 2_000


def test_prejuizo_por_dia_escala_junto():
    """Lucro negativo por dia é informação: perde-se mais rápido produzindo mais."""
    r = daily_yield(unit_profit=-50, focus_per_unit=10, focus_per_day=1_000,
                    market_units_per_day=1_000)
    assert r.profit == pytest.approx(-5_000)
