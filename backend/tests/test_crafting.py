"""Economia de craft: parâmetros explícitos, ausência vira UNKNOWN."""

import pytest

from app.calculations.crafting import MaterialCost, compute_craft
from app.calculations.fees import FeeProfile
from app.calculations.station import StationFee, station_fee_for

TAXAS = FeeProfile(setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True)

MATERIAIS = [
    MaterialCost("T4_WOOD", "Madeira", 2, 1000, is_returnable=True),
    MaterialCost("T3_PLANKS", "Tábuas T3", 1, 800, is_returnable=True),
]


def craft(**overrides):
    base = dict(
        materials=MATERIAIS, sell_price=4000, fees=TAXAS,
        return_rate=0.15, station_fee=taxa(100), output_quantity=1, focus_cost=54, crafts=1,
    )
    return compute_craft(**(base | overrides))


def taxa(silver: float | None) -> StationFee:
    """Taxa de estação já resolvida em prata.

    A taxa deixou de ser um número avulso na fase 15: ela sai do `item_value`
    do item e da prata por 100 de nutrição da estação. Aqui os testes de craft
    só precisam do resultado, então o atalho é construir a taxa direto — quem
    cobre a derivação é `test_station.py`.
    """
    if silver is None:
        return StationFee(silver=None, reason="não informada")
    return StationFee(silver=silver, item_value=0.0, nutrition=0.0,
                      fee_per_100_nutrition=0.0)


class TestParametrosAusentes:
    def test_sem_taxa_de_retorno_e_unknown(self):
        resultado = craft(return_rate=None)
        assert resultado.known is False
        assert "crafting.return_rate" in resultado.missing

    def test_sem_taxa_de_estacao_e_unknown(self):
        faltando = craft(station_fee=taxa(None)).missing
        assert "crafting.station_fee_per_100_nutrition" in faltando

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
        cara = craft(station_fee=taxa(5000))
        barata = craft(station_fee=taxa(0))
        assert cara.profit < barata.profit
        assert cara.roi_pct < barata.roi_pct

    def test_a_taxa_do_t8_e_64_vezes_a_do_t2_e_isso_muda_o_lucro(self):
        """O valor fixo de 100 dizia que refinar T2 e T8 custa a mesma taxa.

        Com a taxa derivada, o T8 paga 2.880 onde o T2 paga 45 — e é a diferença
        entre um lucro que existe e um que não existe.
        """
        t2 = craft(station_fee=station_fee_for(4.0, 1000.0))
        t8 = craft(station_fee=station_fee_for(256.0, 1000.0))
        assert t2.station_fee == pytest.approx(4.5)
        assert t8.station_fee == pytest.approx(288.0)
        assert t8.profit < t2.profit

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
