"""Economia de craft: parâmetros explícitos, ausência vira UNKNOWN."""

import pytest

from app.calculations.crafting import MaterialCost, compute_craft
from app.calculations.fees import FeeProfile

TAXAS = FeeProfile(setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True)

MATERIAIS = [
    MaterialCost("T4_WOOD", "Madeira", 2, 1000, is_returnable=True),
    MaterialCost("T3_PLANKS", "Tábuas T3", 1, 800, is_returnable=True),
]


def craft(**overrides):
    base = dict(
        materials=MATERIAIS, sell_price=4000, fees=TAXAS,
        return_rate=0.15, station_fee=100, output_quantity=1, focus_cost=54, crafts=1,
    )
    return compute_craft(**(base | overrides))


class TestParametrosAusentes:
    def test_sem_taxa_de_retorno_e_unknown(self):
        resultado = craft(return_rate=None)
        assert resultado.known is False
        assert "crafting.return_rate" in resultado.missing

    def test_sem_taxa_de_estacao_e_unknown(self):
        assert "crafting.station_fee" in craft(station_fee=None).missing

    def test_sem_impostos_e_unknown(self):
        resultado = craft(fees=FeeProfile())
        assert resultado.known is False
        assert any("sales_tax" in item for item in resultado.missing)

    def test_material_sem_cotacao_derruba_o_craft_inteiro(self):
        """Um material sem preço torna o custo total desconhecido, não menor."""
        sem_preco = [
            MaterialCost("T4_WOOD", "Madeira", 2, None, is_returnable=True),
            MATERIAIS[1],
        ]
        resultado = craft(materials=sem_preco)
        assert resultado.known is False
        assert "T4_WOOD" in resultado.reason

    def test_sem_preco_de_venda(self):
        assert craft(sell_price=None).known is False

    def test_receita_vazia(self):
        assert craft(materials=[]).known is False


class TestCalculo:
    def test_retorno_reduz_o_custo(self):
        com = craft(return_rate=0.30)
        sem = craft(return_rate=0.0)
        assert com.material_cost_net < sem.material_cost_net
        assert com.profit > sem.profit

    def test_material_nao_elegivel_fica_fora_do_retorno(self):
        """Token de facção não volta. Tratar igual infla o lucro."""
        com_token = [
            *MATERIAIS,
            MaterialCost("T1_FACTION_TOKEN", "Token", 1, 5000, is_returnable=False),
        ]
        resultado = craft(materials=com_token, return_rate=0.5)
        # Base do retorno: só os 2.800 dos materiais elegíveis.
        assert resultado.returned_value == pytest.approx(2800 * 0.5)

    def test_taxa_de_estacao_entra_no_custo_e_no_roi(self):
        cara = craft(station_fee=5000)
        barata = craft(station_fee=0)
        assert cara.profit < barata.profit
        assert cara.roi_pct < barata.roi_pct

    def test_prata_por_focus(self):
        resultado = craft(focus_cost=54)
        assert resultado.profit_per_focus == pytest.approx(resultado.profit / 54, abs=0.01)

    def test_sem_focus_a_metrica_nao_e_inventada(self):
        """Divisão por zero não vira número grande; vira None."""
        assert craft(focus_cost=0).profit_per_focus is None

    def test_lucro_absoluto_alto_pode_ter_prata_por_focus_pior(self):
        """É por isso que o ranking da fase 9 ordena por prata/focus."""
        barato = craft(focus_cost=10)
        caro = craft(sell_price=4400, focus_cost=200)
        assert caro.profit > barato.profit
        assert caro.profit_per_focus < barato.profit_per_focus

    def test_varias_execucoes_escalam_linearmente(self):
        uma = craft(crafts=1)
        dez = craft(crafts=10)
        assert dez.profit == pytest.approx(uma.profit * 10, abs=0.5)
        assert dez.focus_cost == uma.focus_cost * 10

    def test_receita_que_produz_mais_de_uma_unidade(self):
        uma = craft(output_quantity=1)
        tres = craft(output_quantity=3)
        assert tres.output_quantity == 3
        assert tres.profit > uma.profit

    def test_craft_pode_dar_prejuizo(self):
        assert craft(sell_price=1500).profit < 0
