"""Custo ao longo da cadeia de refino.

Cadeia sintética que espelha a real: cada tier refinado consome 2× o bruto do
mesmo tier + 1× o refinado do tier anterior.
"""

import pytest

from app.calculations.chain import (
    MAX_DEPTH,
    ChainCache,
    RecipeSpec,
    Sourcing,
    resolve_unit_cost,
)

PRECOS = {
    "T2_WOOD": 50, "T3_WOOD": 120, "T4_WOOD": 300, "T5_WOOD": 900,
    "T2_PLANKS": 130, "T3_PLANKS": 400, "T4_PLANKS": 1100, "T5_PLANKS": 3800,
}

RECEITAS = {
    "T3_PLANKS": RecipeSpec(1, 20, (("T3_WOOD", 2, True), ("T2_PLANKS", 1, True))),
    "T4_PLANKS": RecipeSpec(1, 54, (("T4_WOOD", 2, True), ("T3_PLANKS", 1, True))),
    "T5_PLANKS": RecipeSpec(1, 118, (("T5_WOOD", 2, True), ("T4_PLANKS", 1, True))),
}


def _variantes(tabela):
    """Adapta um dicionário de receita única à assinatura de variantes.

    `resolve_unit_cost` passou a receber **todas** as variantes na fase 19, para
    poder escolher a mais barata. Estes testes tratam do caminho de uma
    variante só.
    """
    def buscar(nome):
        receita = tabela.get(nome)
        return [receita] if receita is not None else []
    return buscar


def resolver(nome, sourcing, precos=None, retorno=0.15, estacao=100):
    tabela = PRECOS if precos is None else precos
    return resolve_unit_cost(
        nome, sourcing,
        market_price=lambda item: tabela.get(item),
        recipes_for=_variantes(RECEITAS),
        return_rate=retorno, station_fee_of=lambda _nome: estacao,
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
            recipes_for=_variantes(ciclicas),
            return_rate=0.15, station_fee_of=lambda _nome: 100,
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
            recipes_for=_variantes(fundas),
            return_rate=0.15, station_fee_of=lambda _nome: 0,
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


class TestVariantes:
    """A receita tem alternativas, e a mais barata deve vencer.

    Até a fase 19 o motor usava sempre a `variant_index` 0 e ignorava em
    silêncio a variante com token de facção — que muda bastante o custo.
    """

    # T4_PLANKS sai de 2× madeira, **ou** de 1× madeira + 1 token.
    SEM_TOKEN = RecipeSpec(1, 54, (("T4_WOOD", 2, True),), variant_index=0, label="sem token")
    COM_TOKEN = RecipeSpec(
        1, 54, (("T4_WOOD", 1, True), ("TOKEN", 1, False)),
        variant_index=1, label="com token de facção",
    )

    def resolver(self, precos):
        return resolve_unit_cost(
            "T4_PLANKS",
            Sourcing.CRAFT,
            market_price=precos.get,
            recipes_for=lambda n: [self.SEM_TOKEN, self.COM_TOKEN] if n == "T4_PLANKS" else [],
            return_rate=0.0,
            station_fee_of=lambda _n: 0,
        )

    def test_token_barato_vence(self):
        """Token custando pouco: 1 madeira + token sai menos que 2 madeiras."""
        resultado = self.resolver({"T4_WOOD": 300, "TOKEN": 10})
        passo = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo.unit_cost == 310
        assert passo.variant_label == "com token de facção"

    def test_token_caro_perde(self):
        resultado = self.resolver({"T4_WOOD": 300, "TOKEN": 5000})
        passo = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo.unit_cost == 600
        assert passo.variant_label == "sem token"

    def test_a_variante_descartada_vai_na_resposta(self):
        """Quem tem token parado no inventário precisa saber que existe a rota."""
        resultado = self.resolver({"T4_WOOD": 300, "TOKEN": 5000})
        passo = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo.alternative_cost == 5300
        assert passo.alternative_label == "com token de facção"

    def test_variante_sem_cotacao_nao_derruba_a_outra(self):
        """Sem preço de token, a variante base ainda responde."""
        resultado = self.resolver({"T4_WOOD": 300})
        passo = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo.unit_cost == 600
        assert passo.alternative_cost is None

    def test_uma_variante_so_nao_inventa_alternativa(self):
        resultado = resolve_unit_cost(
            "T4_PLANKS", Sourcing.CRAFT,
            market_price={"T4_WOOD": 300}.get,
            recipes_for=lambda n: [self.SEM_TOKEN] if n == "T4_PLANKS" else [],
            return_rate=0.0, station_fee_of=lambda _n: 0,
        )
        passo = next(p for p in resultado.steps if p.unique_name == "T4_PLANKS")
        assert passo.alternative_cost is None
        assert passo.alternative_label is None


class TestMemoizacao:
    """A cadeia compartilha subárvores, e sem memória cada caminho recalcula.

    Medido em `/refining` com 200 oportunidades antes do cache: **51.407**
    chamadas a `resolve_unit_cost`, cerca de 250 por oportunidade, num grafo de
    sete níveis. O T6 é insumo do T7 **e** do T8, e cada um resolvia o seu.

    Estes testes travam a **contagem**. Sem eles, quebrar a memoização não
    quebra nada visível — só deixa a tela lenta de novo, em silêncio, e o
    próximo a medir refaz esta investigação do zero.
    """

    def contador(self, tabela=None):
        """Envolve `recipes_for` para contar quantos nós foram percorridos."""
        buscar = _variantes(RECEITAS if tabela is None else tabela)
        chamadas: list[str] = []

        def espiao(nome):
            chamadas.append(nome)
            return buscar(nome)

        return espiao, chamadas

    def resolver_com(self, nomes, cache, espiao, retorno=0.15):
        return [
            resolve_unit_cost(
                nome, Sourcing.CRAFT,
                market_price=lambda item: PRECOS.get(item),
                recipes_for=espiao,
                return_rate=retorno,
                station_fee_of=lambda _n: 100,
                cache=cache,
            )
            for nome in nomes
        ]

    def test_sem_cache_cada_item_refaz_a_cadeia_inteira(self):
        espiao, chamadas = self.contador()
        self.resolver_com(["T3_PLANKS", "T4_PLANKS", "T5_PLANKS"], None, espiao)
        # T3 percorre 3 nós, T4 percorre 5 e T5 percorre 7 — e os de baixo
        # são os mesmos, refeitos. 3 + 5 + 7 = 15 para sete nós distintos.
        assert len(chamadas) == 15
        assert len(set(chamadas)) == 7

    def test_com_cache_cada_no_e_percorrido_uma_vez(self):
        cache = ChainCache()
        espiao, chamadas = self.contador()
        self.resolver_com(["T3_PLANKS", "T4_PLANKS", "T5_PLANKS"], cache, espiao)
        # Os mesmos sete nós, uma vez cada: 15 → 7. Numa cadeia de três
        # itens a economia é de metade; em `/refining`, com 200 itens e sete
        # tiers, foi de 51.407 para uma fração disso.
        assert len(set(chamadas)) == len(chamadas) == 7
        assert cache.acertos > 0
        assert cache.calculos == 7

    def test_o_resultado_e_o_mesmo_com_e_sem_cache(self):
        """A memória não pode mudar número. É o que a torna aplicável."""
        espiao_a, _ = self.contador()
        espiao_b, _ = self.contador()
        sem = self.resolver_com(["T5_PLANKS"], None, espiao_a)[0]
        com = self.resolver_com(["T5_PLANKS"], ChainCache(), espiao_b)[0]
        assert com.unit_cost == sem.unit_cost
        assert com.focus_per_unit == sem.focus_per_unit
        assert [p.unique_name for p in com.steps] == [p.unique_name for p in sem.steps]
        assert [p.depth for p in com.steps] == [p.depth for p in sem.steps]

    def test_a_profundidade_dos_passos_e_reescrita_no_acerto(self):
        """O mesmo item aparece em níveis diferentes conforme quem o pediu.

        `ChainStep.depth` é o que desenha a árvore. Devolver o passo com a
        profundidade de onde ele foi calculado mostraria a cadeia com a forma
        errada — e, como o custo estaria certo, ninguém desconfiaria do desenho.
        """
        cache = ChainCache()
        espiao, _ = self.contador()
        # T4 primeiro (T3 fica guardado no nível 1), depois T5 (T3 vem no 2).
        [t4, t5] = self.resolver_com(["T4_PLANKS", "T5_PLANKS"], cache, espiao)
        nivel = {p.unique_name: p.depth for p in t4.steps}
        assert nivel["T3_PLANKS"] == 1
        nivel = {p.unique_name: p.depth for p in t5.steps}
        assert nivel["T4_PLANKS"] == 1
        assert nivel["T3_PLANKS"] == 2

    def test_taxas_de_retorno_diferentes_nao_se_misturam(self):
        """O retorno varia por item — ele segue a família e a cidade.

        Dois itens da mesma requisição podem ter taxas diferentes, e é por isso
        que a taxa entra na chave. Fora dela, o segundo item receberia o custo
        do primeiro.
        """
        cache = ChainCache()
        espiao, _ = self.contador()
        a = self.resolver_com(["T5_PLANKS"], cache, espiao, retorno=0.15)[0]
        b = self.resolver_com(["T5_PLANKS"], cache, espiao, retorno=0.40)[0]
        assert a.unit_cost != b.unit_cost

    def test_sourcings_diferentes_nao_se_misturam(self):
        cache = ChainCache()
        espiao, _ = self.contador()
        produzir = resolve_unit_cost(
            "T5_PLANKS", Sourcing.CRAFT, lambda i: PRECOS.get(i), espiao,
            0.15, lambda _n: 100, cache=cache,
        )
        mercado = resolve_unit_cost(
            "T5_PLANKS", Sourcing.MARKET, lambda i: PRECOS.get(i), espiao,
            0.15, lambda _n: 100, cache=cache,
        )
        assert mercado.unit_cost == 3800
        assert produzir.unit_cost != mercado.unit_cost

    def test_ciclo_no_dump_desliga_o_cache_em_vez_de_mentir(self):
        """O corte de ciclo depende do caminho, e o cache indexa por item.

        Num grafo acíclico isto nunca acontece. Se o dump tiver ciclo, o cache
        se desliga e esquece o que sabia: volta a ser lento e correto, em vez de
        servir a resposta de um caminho para outro.
        """
        ciclica = {
            "A": RecipeSpec(1, 10, (("B", 1, True),)),
            "B": RecipeSpec(1, 10, (("A", 1, True),)),
        }
        cache = ChainCache()
        espiao, _ = self.contador(ciclica)
        resolve_unit_cost(
            "A", Sourcing.CRAFT, lambda _i: 100, espiao, 0.15, lambda _n: 100, cache=cache
        )
        assert cache.habilitada is False
