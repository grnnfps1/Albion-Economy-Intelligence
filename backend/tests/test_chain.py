"""Custo ao longo da cadeia de refino.

Cadeia sintética que espelha a real: cada tier refinado consome 2× o bruto do
mesmo tier + 1× o refinado do tier anterior.
"""

import pytest

from app.calculations.chain import MAX_DEPTH, RecipeSpec, Sourcing, resolve_unit_cost

PRECOS = {
    "T2_WOOD": 50, "T3_WOOD": 120, "T4_WOOD": 300, "T5_WOOD": 900,
    "T2_PLANKS": 130, "T3_PLANKS": 400, "T4_PLANKS": 1100, "T5_PLANKS": 3800,
}

RECEITAS = {
    "T3_PLANKS": RecipeSpec(1, 20, (("T3_WOOD", 2, True), ("T2_PLANKS", 1, True))),
    "T4_PLANKS": RecipeSpec(1, 54, (("T4_WOOD", 2, True), ("T3_PLANKS", 1, True))),
    "T5_PLANKS": RecipeSpec(1, 118, (("T5_WOOD", 2, True), ("T4_PLANKS", 1, True))),
}


def resolver(nome, sourcing, precos=None, retorno=0.15, estacao=100):
    tabela = PRECOS if precos is None else precos
    return resolve_unit_cost(
        nome, sourcing,
        market_price=lambda item: tabela.get(item),
        recipe_for=RECEITAS.get,
        return_rate=retorno, station_fee=estacao,
    )


class TestMercado:
    def test_usa_o_preco_direto(self):
        resultado = resolver("T5_PLANKS", Sourcing.MARKET)
        assert resultado.unit_cost == 3800
        assert resultado.focus_per_unit == 0
        assert len(resultado.steps) == 1

    def test_sem_cotacao_e_unknown(self):
        resultado = resolver("T8_PLANKS", Sourcing.MARKET)
        assert resultado.known is False
        assert "sem cotação" in resultado.reason


class TestProduzir:
    def test_desce_a_cadeia_inteira(self):
        """T5 → T4 → T3 → T2, e o bruto de cada tier."""
        resultado = resolver("T5_PLANKS", Sourcing.CRAFT)
        assert resultado.known is True
        visitados = {passo.unique_name for passo in resultado.steps}
        assert {"T5_WOOD", "T4_PLANKS", "T3_PLANKS", "T2_PLANKS", "T3_WOOD"} <= visitados

    def test_focus_acumula_so_no_que_se_produz(self):
        mercado = resolver("T5_PLANKS", Sourcing.MARKET)
        produzir = resolver("T5_PLANKS", Sourcing.CRAFT)
        assert mercado.focus_per_unit == 0
        assert produzir.focus_per_unit > 0

    def test_retorno_maior_baixa_o_custo_de_producao(self):
        caro = resolver("T5_PLANKS", Sourcing.CRAFT, retorno=0.0)
        barato = resolver("T5_PLANKS", Sourcing.CRAFT, retorno=0.5)
        assert barato.unit_cost < caro.unit_cost

    def test_taxa_de_estacao_encarece_cada_elo(self):
        """Cada passo da cadeia paga a taxa, não só o último."""
        sem = resolver("T5_PLANKS", Sourcing.CRAFT, estacao=0)
        com = resolver("T5_PLANKS", Sourcing.CRAFT, estacao=1000)
        # Quatro elos de refino: o efeito é maior que uma única taxa.
        assert com.unit_cost - sem.unit_cost > 1000

    def test_recurso_bruto_encerra_a_cadeia(self):
        resultado = resolver("T5_WOOD", Sourcing.CRAFT)
        assert resultado.unit_cost == 900
        assert resultado.steps[0].sourcing is Sourcing.MARKET

    def test_parametro_faltando_e_unknown(self):
        resultado = resolver("T5_PLANKS", Sourcing.CRAFT, retorno=None)
        assert resultado.known is False
        assert "crafting.return_rate" in resultado.reason

    def test_material_sem_cotacao_no_meio_da_cadeia(self):
        precos = {k: v for k, v in PRECOS.items() if k != "T3_WOOD"}
        resultado = resolver("T5_PLANKS", Sourcing.CRAFT, precos=precos)
        assert resultado.known is False
        assert "T3_WOOD" in resultado.reason


class TestMaisBarato:
    def test_compra_quando_o_mercado_esta_mais_barato(self):
        """Tier baixo costuma ter preço abaixo do custo: muita gente refina
        com bônus de cidade e o mercado desaba."""
        precos = {**PRECOS, "T4_PLANKS": 1}
        resultado = resolver("T5_PLANKS", Sourcing.CHEAPEST, precos=precos)
        passo_t4 = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo_t4.sourcing is Sourcing.MARKET
        assert passo_t4.unit_cost == 1

    def test_produz_quando_o_mercado_esta_caro(self):
        precos = {**PRECOS, "T4_PLANKS": 999_999}
        resultado = resolver("T5_PLANKS", Sourcing.CHEAPEST, precos=precos)
        passo_t4 = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo_t4.sourcing is Sourcing.CRAFT

    def test_nunca_custa_mais_que_as_duas_alternativas_puras(self):
        barato = resolver("T5_PLANKS", Sourcing.CHEAPEST)
        mercado = resolver("T5_PLANKS", Sourcing.MARKET)
        produzir = resolver("T5_PLANKS", Sourcing.CRAFT)
        assert barato.unit_cost <= min(mercado.unit_cost, produzir.unit_cost) + 1e-6

    def test_cada_passo_registra_a_escolha(self):
        """Sem isso, o usuário vê um custo e não sabe o que comprar."""
        resultado = resolver("T5_PLANKS", Sourcing.CHEAPEST)
        assert all(passo.sourcing in (Sourcing.MARKET, Sourcing.CRAFT) for passo in resultado.steps)


class TestProtecoes:
    def test_ciclo_na_receita_nao_estoura_a_pilha(self):
        """Dump malformado não pode derrubar a API."""
        ciclicas = {
            "A": RecipeSpec(1, 10, (("B", 1, True),)),
            "B": RecipeSpec(1, 10, (("A", 1, True),)),
        }
        resultado = resolve_unit_cost(
            "A", Sourcing.CRAFT,
            market_price=lambda item: 100,
            recipe_for=ciclicas.get,
            return_rate=0.15, station_fee=100,
        )
        assert resultado.known is True

    def test_profundidade_e_limitada(self):
        fundas = {
            f"N{i}": RecipeSpec(1, 1, ((f"N{i + 1}", 1, True),))
            for i in range(MAX_DEPTH + 5)
        }
        resultado = resolve_unit_cost(
            "N0", Sourcing.CRAFT,
            market_price=lambda item: 10,
            recipe_for=fundas.get,
            return_rate=0.15, station_fee=0,
        )
        assert resultado.known is True
        assert max(p.depth for p in resultado.steps) <= MAX_DEPTH


def test_produzir_pode_ser_pior_que_comprar():
    """O produto precisa dizer isso, não esconder."""
    precos = {**PRECOS, "T5_WOOD": 5000}
    mercado = resolver("T5_PLANKS", Sourcing.MARKET, precos=precos)
    produzir = resolver("T5_PLANKS", Sourcing.CRAFT, precos=precos)
    assert produzir.unit_cost > mercado.unit_cost
    assert pytest.approx(mercado.unit_cost) == 3800
