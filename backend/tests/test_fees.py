"""Economia de operação: taxas explícitas, ausência vira UNKNOWN."""

import pytest

from app.calculations.fees import FeeProfile, Strategy, compute_trade

# Valores de exemplo. Não são os do jogo — os reais ainda não foram medidos
# (docs/04-taxas.md). Servem para verificar a fórmula, não a realidade.
TAXAS = FeeProfile(setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True)


class TestParametrosAusentes:
    def test_sem_taxas_o_resultado_e_unknown(self):
        """Requisito 52: margem sem imposto é sempre otimista."""
        resultado = compute_trade(1000, 1500, FeeProfile(), Strategy.FAST)
        assert resultado.known is False
        assert "taxas não configuradas" in resultado.reason

    def test_reason_diz_o_que_falta(self):
        """Sem isso o usuário não sabe o que preencher para destravar."""
        parcial = FeeProfile(setup_fee_pct=0.025)
        resultado = compute_trade(1000, 1500, parcial, Strategy.FAST)
        assert "sales_tax" in resultado.reason

    def test_sem_cotacao_em_uma_ponta(self):
        resultado = compute_trade(None, 1500, TAXAS, Strategy.FAST)
        assert resultado.known is False
        assert "sem cotação" in resultado.reason

    def test_preco_zero_nao_e_tratado_como_preco(self):
        assert compute_trade(0, 1500, TAXAS, Strategy.FAST).known is False

    def test_quantidade_invalida(self):
        assert compute_trade(1000, 1500, TAXAS, Strategy.FAST, quantity=0).known is False


class TestEstrategiaImediata:
    def test_nao_paga_setup_fee(self):
        """Consumir ordem existente não cria ordem nenhuma."""
        r = compute_trade(1000, 1500, TAXAS, Strategy.FAST, quantity=100)
        assert r.known is True
        # Só o imposto de venda: 1500 * 4% * 100
        assert r.fees == pytest.approx(6000.0)
        assert r.net_profit == pytest.approx((1500 * 0.96 - 1000) * 100)

    def test_margem_e_roi_medem_coisas_diferentes(self):
        r = compute_trade(1000, 1500, TAXAS, Strategy.FAST, quantity=100)
        # Margem sobre receita bruta; ROI sobre capital imobilizado.
        assert r.margin_pct == pytest.approx(r.net_profit / r.gross_revenue * 100, abs=0.01)
        assert r.roi_pct == pytest.approx(r.net_profit / r.investment * 100, abs=0.01)
        assert r.roi_pct > r.margin_pct


class TestEstrategiaPaciente:
    def test_paga_setup_fee_nas_duas_pontas(self):
        imediata = compute_trade(1000, 1500, TAXAS, Strategy.FAST, quantity=100)
        paciente = compute_trade(1000, 1500, TAXAS, Strategy.PATIENT, quantity=100)
        assert paciente.fees > imediata.fees
        assert paciente.net_profit < imediata.net_profit

    def test_spread_que_parece_lucrativo_pode_ser_prejuizo(self):
        """Spread de 5% não cobre setup duplo mais imposto."""
        r = compute_trade(1000, 1050, TAXAS, Strategy.PATIENT, quantity=100)
        assert r.known is True
        assert r.net_profit < 0


class TestTransporte:
    def test_transporte_entra_no_custo_e_no_roi(self):
        sem = compute_trade(1000, 1500, TAXAS, Strategy.FAST, quantity=100)
        com = compute_trade(
            1000, 1500, TAXAS, Strategy.FAST, quantity=100, transport_cost_per_unit=50
        )
        assert com.transport_cost == pytest.approx(5000.0)
        assert com.net_profit == pytest.approx(sem.net_profit - 5000.0)
        assert com.investment > sem.investment

    def test_transporte_caro_inverte_o_sinal(self):
        r = compute_trade(
            1000, 1100, TAXAS, Strategy.FAST, quantity=100, transport_cost_per_unit=200
        )
        assert r.net_profit < 0
