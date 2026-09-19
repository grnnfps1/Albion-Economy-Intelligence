"""Economia de craft: parâmetros explícitos, ausência vira UNKNOWN."""

import pytest

from app.calculations.crafting import MaterialCost, compute_craft
from app.calculations.fees import FeeProfile, Strategy
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


class TestEscalaPelaQuantidade:
    """O calculador exibe por unidade e escala pelo campo "Quantidade".

    A divisão entre o que escala e o que não escala é a própria definição de
    grandeza extensiva e intensiva, e trocá-las é um bug que passa despercebido:
    uma margem que sobe com a quantidade parece "produzir mais compensa mais" e
    não denuncia nada.
    """

    EXTENSIVAS = [
        "material_cost_gross",
        "material_cost_net",
        "returned_value",
        "station_fee",
        "sale_revenue_net",
        "market_fees",
        "production_cost",
        "profit",
        "focus_cost",
    ]

    @pytest.mark.parametrize("campo", EXTENSIVAS)
    def test_escalam_linearmente(self, campo):
        uma = craft(crafts=1)
        dez_mil = craft(crafts=10_000)
        assert getattr(dez_mil, campo) == pytest.approx(
            getattr(uma, campo) * 10_000, rel=1e-9
        )

    @pytest.mark.parametrize("campo", ["margin_pct", "margin_on_cost_pct", "roi_pct",
                                       "profit_per_focus"])
    def test_as_razoes_ficam_identicas(self, campo):
        """Margem, ROI e prata/focus são razões: `crafts` se cancela.

        Se variarem, há arredondamento aplicado cedo demais — foi exatamente o
        que acontecia quando o custo de produção era somado a partir dos campos
        já arredondados, em vez de vir pronto de `compute_craft`.
        """
        assert getattr(craft(crafts=10_000), campo) == getattr(craft(crafts=1), campo)

    def test_o_investimento_tambem_escala(self):
        """Não há campo `investment`; ele é `bruto + estação`, e é o que a tela mostra."""
        uma = craft(crafts=1)
        mil = craft(crafts=1_000)
        assert (mil.material_cost_gross + mil.station_fee) == pytest.approx(
            (uma.material_cost_gross + uma.station_fee) * 1_000, rel=1e-9
        )

    def test_a_taxa_da_estacao_e_por_craft_e_nao_fixa_da_sessao(self):
        """500 execuções pagam 500 vezes — a estação cobra nutrição por craft.

        Se fosse taxa fixa de sessão, ela apareceria igual nas duas chamadas, e
        o lucro por unidade melhoraria só por produzir em lote. Não melhora.
        """
        assert craft(crafts=500).station_fee == pytest.approx(
            craft(crafts=1).station_fee * 500
        )

    def test_lucro_por_unidade_nao_melhora_com_o_lote(self):
        """Corolário: nada aqui tem ganho de escala. Se tivesse, seria invenção."""
        uma = craft(crafts=1)
        mil = craft(crafts=1_000)
        assert mil.profit / 1_000 == pytest.approx(uma.profit, rel=1e-9)

    def test_as_razoes_sao_identicas_em_qualquer_linha(self):
        """Varredura: nenhuma combinação de preço, receita e saída escapa.

        Os três exemplos fixos acima passavam **antes** do conserto — a
        divergência aparecia em 11 de 20.000 combinações, sempre no último
        dígito, e sempre perto de x,xx5. Um teste de exemplo único não pegaria;
        por isso este varre.
        """
        divergentes = []
        for preco in range(3, 400, 37):
            for multiplicador in (2, 3, 5, 8):
                for saida in (1, 2, 5):
                    mats = [MaterialCost("T2_HIDE", "x", 3, preco, is_returnable=True)]
                    razoes = set()
                    for n in (1, 7, 10_000):
                        e = compute_craft(
                            materials=mats, sell_price=preco * multiplicador, fees=TAXAS,
                            return_rate=0.3671, station_fee=taxa(0.37),
                            output_quantity=saida, focus_cost=54, crafts=n,
                            strategy=Strategy.PATIENT,
                        )
                        razoes.add(
                            (e.margin_pct, e.margin_on_cost_pct, e.roi_pct, e.profit_per_focus)
                        )
                    if len(razoes) > 1:
                        divergentes.append((preco, multiplicador, saida, razoes))
        assert divergentes == []
