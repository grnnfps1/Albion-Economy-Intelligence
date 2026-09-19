"""Custo de um item ao longo da cadeia de refino.

O refino encadeia: `T5_PLANKS` precisa de `T4_PLANKS`, que precisa de
`T3_PLANKS`. Isso cria uma pergunta que crafting de item final não tem:

    o insumo do tier anterior custa o preço de mercado, ou custa o que custaria
    refiná-lo você mesmo?

São respostas diferentes, e as duas estão certas dependendo de quem pergunta.
Quem compra tudo pronto usa mercado. Quem já tem a cadeia montada usa o custo de
produção — e para essa pessoa a resposta do mercado superestima o custo sempre
que refinar sai mais barato do que comprar.

O motor calcula as duas e deixa a escolha explícita. Funções puras: a busca de
preço e de receita chega como callable, então dá para testar a cadeia inteira
sem banco.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum


class Sourcing(StrEnum):
    MARKET = "MERCADO"
    """Comprar o insumo pronto."""

    CRAFT = "PRODUZIR"
    """Produzir o insumo a partir da receita dele."""

    CHEAPEST = "MAIS_BARATO"
    """Escolher, tier a tier, o menor entre os dois."""


@dataclass(frozen=True)
class RecipeSpec:
    """Receita reduzida ao que o cálculo de cadeia precisa."""

    output_quantity: int
    focus_cost: float
    """Focus por lote, **já reduzido pela especialização** do usuário.

    A redução é política e mora em `services/specialization_service.py`; a
    cadeia recebe o número pronto e segue sem saber que spec existe.
    """
    materials: tuple[tuple[str, int, bool], ...]
    """(unique_name, quantidade, elegível ao retorno)"""

    variant_index: int = 0
    label: str | None = None
    """Como a variante se chama para quem lê. Ex.: "com token de facção".

    Quem rotula é o serviço: a cadeia não sabe o que é um token, só que há mais
    de um jeito de fazer o mesmo item.
    """


@dataclass
class ChainStep:
    unique_name: str
    sourcing: Sourcing
    unit_cost: float | None
    market_price: int | None
    craft_cost: float | None
    focus_per_unit: float = 0.0
    depth: int = 0
    reason: str | None = None

    variant_index: int = 0
    variant_label: str | None = None
    alternative_cost: float | None = None
    """Custo da melhor variante **descartada**, quando havia mais de uma.

    Vai para a resposta de propósito: com token de facção o custo muda muito, e
    quem tem token parado no inventário precisa saber que existe o caminho —
    mesmo quando o motor escolheu o outro.
    """
    alternative_label: str | None = None

    @property
    def known(self) -> bool:
        return self.unit_cost is not None


@dataclass
class ChainResult:
    unit_cost: float | None
    focus_per_unit: float
    steps: list[ChainStep] = field(default_factory=list)
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.unit_cost is not None


# Profundidade máxima da recursão. T2→T8 são seis passos; 10 dá folga e ainda
# corta qualquer ciclo que um dump malformado introduza.
MAX_DEPTH = 10


@dataclass
class ChainCache:
    """Memoização da cadeia, **por requisição**.

    ## Por que existe

    A cadeia T2→T8 compartilha subárvores: o T6 é insumo do T7 **e** do T8, e
    cada caminho recalculava a dele. Medido em `/refining` com 200
    oportunidades: 51.407 chamadas a `resolve_unit_cost`, cerca de 250 por
    oportunidade, para um grafo que tem sete níveis.

    ## Por que nunca é global

    Preço muda. Um cache entre requisições devolveria custo calculado com a
    cotação de ontem, silenciosamente — exatamente a classe de erro que a regra
    1 existe para evitar, só que pior, porque o número **parece** fresco. O
    dono do ciclo de vida é quem atende a requisição.

    ## O que a chave precisa carregar, e o que não

    Na chave: `unique_name`, `sourcing` e `return_rate`. O retorno **varia por
    item** — ele depende da família do recurso e da cidade —, então dois itens
    da mesma requisição podem ter taxas diferentes, e misturá-las daria o custo
    de um com a taxa do outro.

    Fora da chave, e por isso **invariante do cache**: `market_price`,
    `recipes_for` e `station_fee_of`. Um `ChainCache` pertence a um conjunto
    fixo dessas três funções. `refining_service` mantém dois caches justamente
    por causa disso — um para `price_of` e outro para `base_price_of`, que são
    dois preços diferentes para o mesmo item.

    ## Ciclo desliga o cache

    O corte de ciclo depende do **caminho** (`_visiting`), e um resultado
    calculado sob um caminho não vale para outro. Num grafo acíclico isso nunca
    morde, porque a subárvore de um item nunca contém um ancestral dele. Se o
    dump tiver ciclo, o cache se desliga e esquece o que sabia — voltando ao
    comportamento de antes, que é lento e correto.
    """

    _por_chave: dict[tuple[str, Sourcing, float | None], tuple["ChainResult", int]] = field(
        default_factory=dict
    )
    habilitada: bool = True

    acertos: int = 0
    """Quantas vezes a subárvore já estava resolvida. É o ganho, medível."""

    calculos: int = 0
    """Quantas subárvores foram de fato percorridas."""

    def desabilitar_por_ciclo(self) -> None:
        self.habilitada = False
        self._por_chave.clear()

    def obter(
        self, chave: tuple[str, Sourcing, float | None], depth: int
    ) -> "ChainResult | None":
        if not self.habilitada:
            return None
        guardado = self._por_chave.get(chave)
        if guardado is None:
            return None
        self.acertos += 1
        resultado, depth_original = guardado
        return _rebase(resultado, depth_original, depth)

    def guardar(
        self, chave: tuple[str, Sourcing, float | None], depth: int, resultado: "ChainResult"
    ) -> None:
        if self.habilitada:
            self._por_chave[chave] = (resultado, depth)


def _rebase(resultado: "ChainResult", de: int, para: int) -> "ChainResult":
    """O mesmo resultado, com os passos renumerados para a nova profundidade.

    `ChainStep.depth` é o que desenha a cadeia na tela. Reaproveitar um
    resultado calculado a três níveis de profundidade, num ponto que está a
    cinco, mostraria a árvore com a forma errada — e como o custo estaria certo,
    ninguém desconfiaria do desenho.
    """
    if de == para or not resultado.steps:
        return resultado
    delta = para - de
    return replace(
        resultado,
        steps=[replace(passo, depth=passo.depth + delta) for passo in resultado.steps],
    )


def resolve_unit_cost(
    unique_name: str,
    sourcing: Sourcing,
    market_price: Callable[[str], int | None],
    recipes_for: Callable[[str], Sequence[RecipeSpec]],
    return_rate: float | None,
    station_fee_of: Callable[[str], float | None],
    cache: ChainCache | None = None,
    _depth: int = 0,
    _visiting: frozenset[str] = frozenset(),
) -> ChainResult:
    """Custo por unidade de `unique_name`, seguindo a cadeia quando pedido.

    `recipes_for` devolve **todas** as variantes da receita, e a cadeia calcula
    cada uma para ficar com a mais barata. Até a fase 19 ela recebia uma só, e o
    serviço entregava sempre a primeira — o que ignorava em silêncio a variante
    com token de facção, que muda bastante o custo. A variante descartada vai na
    resposta, porque quem tem token no inventário precisa saber que ela existe.

    `station_fee_of` é consultada **por elo**, não uma vez para a cadeia toda.
    Desde a fase 15 a taxa da estação sai do valor do item, e o valor do item
    dobra a cada tier: cobrar a taxa do T8 nos seis elos abaixo dele inflaria o
    custo, e cobrar a do T2 em todos o esvaziaria. Cada elo paga pelo que ele
    próprio produz.

    `_visiting` corta ciclos: uma receita que dependesse de si mesma faria a
    recursão rodar até estourar a pilha. Um dump malformado não pode derrubar a
    API.
    """
    if _depth >= MAX_DEPTH or unique_name in _visiting:
        # O corte depende do caminho, e um cache indexado por item não
        # distingue caminhos. Num grafo acíclico isto nunca acontece; se
        # acontecer, o cache se desliga em vez de servir resposta de um
        # caminho para outro.
        if cache is not None and unique_name in _visiting:
            cache.desabilitar_por_ciclo()
        return _apenas_mercado(
            unique_name, market_price(unique_name), _depth, "profundidade máxima ou ciclo"
        )

    chave = (unique_name, sourcing, return_rate)
    if cache is not None:
        guardado = cache.obter(chave, _depth)
        if guardado is not None:
            return guardado
        cache.calculos += 1

    preco = market_price(unique_name)

    if sourcing is Sourcing.MARKET:
        resultado = _apenas_mercado(unique_name, preco, _depth, None)
        if cache is not None:
            cache.guardar(chave, _depth, resultado)
        return resultado

    variantes = [r for r in recipes_for(unique_name) if r.materials]
    if not variantes:
        # Recurso bruto não tem receita. Fim natural da cadeia.
        resultado = _apenas_mercado(unique_name, preco, _depth, None)
        if cache is not None:
            cache.guardar(chave, _depth, resultado)
        return resultado

    station_fee = station_fee_of(unique_name)
    if return_rate is None or station_fee is None:
        faltando = []
        if return_rate is None:
            faltando.append("crafting.return_rate")
        if station_fee is None:
            faltando.append("crafting.station_fee_per_100_nutrition")
        return ChainResult(
            unit_cost=None,
            focus_per_unit=0.0,
            reason="parâmetros não configurados: " + ", ".join(faltando),
        )

    avaliadas: list[_Avaliacao] = []
    ultimo_motivo: str | None = None
    passos_de_falha: list[ChainStep] = []

    for receita in variantes:
        avaliada = _avaliar(
            receita, unique_name, sourcing, market_price, recipes_for,
            return_rate, station_fee, station_fee_of, _depth, _visiting, cache,
        )
        if avaliada is None:
            continue
        if avaliada.custo is None:
            ultimo_motivo = avaliada.reason
            passos_de_falha = avaliada.passos
            continue
        avaliadas.append(avaliada)

    if not avaliadas:
        # Nenhuma variante fecha: o motivo da última é o mais informativo.
        resultado = ChainResult(
            unit_cost=None,
            focus_per_unit=0.0,
            steps=passos_de_falha,
            reason=ultimo_motivo or f"sem custo para {unique_name}",
        )
        if cache is not None:
            cache.guardar(chave, _depth, resultado)
        return resultado

    # A mais barata vence. Empate fica com a primeira, que é a variante base.
    avaliadas.sort(key=lambda a: a.custo)
    vencedora = avaliadas[0]
    descartada = avaliadas[1] if len(avaliadas) > 1 else None

    escolhido, custo = _escolher(sourcing, preco, vencedora.custo)

    passo = ChainStep(
        unique_name=unique_name,
        sourcing=escolhido,
        unit_cost=custo,
        market_price=preco,
        craft_cost=round(vencedora.custo, 2),
        focus_per_unit=round(vencedora.focus, 2) if escolhido is Sourcing.CRAFT else 0.0,
        depth=_depth,
        variant_index=vencedora.receita.variant_index,
        variant_label=vencedora.receita.label,
        alternative_cost=None if descartada is None else round(descartada.custo, 2),
        alternative_label=None if descartada is None else descartada.receita.label,
    )
    passos = [*vencedora.passos, passo]

    resultado = ChainResult(
        unit_cost=custo,
        # Focus só é gasto no que se decide produzir.
        focus_per_unit=vencedora.focus if escolhido is Sourcing.CRAFT else 0.0,
        steps=passos,
    )
    if cache is not None:
        cache.guardar(chave, _depth, resultado)
    return resultado


@dataclass
class _Avaliacao:
    """Uma variante já custeada. `custo=None` significa que ela não fecha."""

    receita: RecipeSpec
    custo: float | None
    focus: float
    passos: list[ChainStep]
    reason: str | None = None


def _avaliar(
    receita: RecipeSpec,
    unique_name: str,
    sourcing: Sourcing,
    market_price: Callable[[str], int | None],
    recipes_for: Callable[[str], Sequence[RecipeSpec]],
    return_rate: float,
    station_fee: float,
    station_fee_of: Callable[[str], float | None],
    depth: int,
    visiting: frozenset[str],
    cache: ChainCache | None = None,
) -> "_Avaliacao | None":
    """Custo por unidade de uma variante específica.

    `station_fee` é a taxa **deste** elo, já resolvida; `station_fee_of` desce
    para os elos abaixo, que pagam a taxa do que eles próprios produzem. Passar
    a taxa deste elo para baixo apagaria a fase 15.
    """
    passos: list[ChainStep] = []
    custo_bruto = 0.0
    base_retorno = 0.0

    for material, quantidade, retorna in receita.materials:
        sub = resolve_unit_cost(
            material, sourcing, market_price, recipes_for, return_rate,
            station_fee_of, cache, depth + 1, visiting | {unique_name},
        )
        passos.extend(sub.steps)
        if not sub.known:
            return _Avaliacao(
                receita=receita, custo=None, focus=0.0, passos=passos,
                reason=sub.reason or f"sem custo para {material}",
            )
        custo_bruto += sub.unit_cost * quantidade
        if retorna:
            base_retorno += sub.unit_cost * quantidade

    por_lote = custo_bruto - base_retorno * return_rate + station_fee
    saida = max(1, receita.output_quantity)
    return _Avaliacao(
        receita=receita,
        custo=por_lote / saida,
        focus=receita.focus_cost / saida,
        passos=passos,
    )


def _apenas_mercado(
    unique_name: str, preco: int | None, depth: int, motivo: str | None
) -> ChainResult:
    passo = ChainStep(
        unique_name=unique_name,
        sourcing=Sourcing.MARKET,
        unit_cost=float(preco) if preco else None,
        market_price=preco,
        craft_cost=None,
        depth=depth,
        reason=motivo if preco is None else None,
    )
    return ChainResult(
        unit_cost=passo.unit_cost,
        focus_per_unit=0.0,
        steps=[passo],
        reason=None if passo.known else f"sem cotação para {unique_name}",
    )


def _escolher(
    sourcing: Sourcing, preco: int | None, custo_producao: float
) -> tuple[Sourcing, float]:
    if sourcing is Sourcing.CRAFT:
        return Sourcing.CRAFT, custo_producao
    # CHEAPEST: comprar pronto quando o mercado está mais barato que produzir.
    # É o caso comum em tiers baixos, onde muita gente refina de graça com bônus
    # de cidade e o preço desaba.
    if preco is not None and preco < custo_producao:
        return Sourcing.MARKET, float(preco)
    return Sourcing.CRAFT, custo_producao
