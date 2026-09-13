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

from collections.abc import Callable
from dataclasses import dataclass, field
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
    focus_cost: int
    materials: tuple[tuple[str, int, bool], ...]
    """(unique_name, quantidade, elegível ao retorno)"""


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


def resolve_unit_cost(
    unique_name: str,
    sourcing: Sourcing,
    market_price: Callable[[str], int | None],
    recipe_for: Callable[[str], RecipeSpec | None],
    return_rate: float | None,
    station_fee: float | None,
    _depth: int = 0,
    _visiting: frozenset[str] = frozenset(),
) -> ChainResult:
    """Custo por unidade de `unique_name`, seguindo a cadeia quando pedido.

    `_visiting` corta ciclos: uma receita que dependesse de si mesma faria a
    recursão rodar até estourar a pilha. Um dump malformado não pode derrubar a
    API.
    """
    preco = market_price(unique_name)

    if _depth >= MAX_DEPTH or unique_name in _visiting:
        return _apenas_mercado(unique_name, preco, _depth, "profundidade máxima ou ciclo")

    if sourcing is Sourcing.MARKET:
        return _apenas_mercado(unique_name, preco, _depth, None)

    receita = recipe_for(unique_name)
    if receita is None or not receita.materials:
        # Recurso bruto não tem receita. Fim natural da cadeia.
        return _apenas_mercado(unique_name, preco, _depth, None)

    if return_rate is None or station_fee is None:
        faltando = []
        if return_rate is None:
            faltando.append("crafting.return_rate")
        if station_fee is None:
            faltando.append("crafting.station_fee")
        return ChainResult(
            unit_cost=None,
            focus_per_unit=0.0,
            reason="parâmetros não configurados: " + ", ".join(faltando),
        )

    passos: list[ChainStep] = []
    custo_bruto = 0.0
    base_retorno = 0.0

    for material, quantidade, retorna in receita.materials:
        sub = resolve_unit_cost(
            material, sourcing, market_price, recipe_for, return_rate,
            station_fee, _depth + 1, _visiting | {unique_name},
        )
        passos.extend(sub.steps)
        if not sub.known:
            return ChainResult(
                unit_cost=None,
                focus_per_unit=0.0,
                steps=passos,
                reason=sub.reason or f"sem custo para {material}",
            )
        custo_bruto += sub.unit_cost * quantidade
        if retorna:
            base_retorno += sub.unit_cost * quantidade

    por_lote = custo_bruto - base_retorno * return_rate + station_fee
    saida = max(1, receita.output_quantity)
    custo_producao = por_lote / saida
    focus_unitario = receita.focus_cost / saida

    escolhido, custo = _escolher(sourcing, preco, custo_producao)

    passo = ChainStep(
        unique_name=unique_name,
        sourcing=escolhido,
        unit_cost=custo,
        market_price=preco,
        craft_cost=round(custo_producao, 2),
        focus_per_unit=round(focus_unitario, 2) if escolhido is Sourcing.CRAFT else 0.0,
        depth=_depth,
    )
    passos.append(passo)

    return ChainResult(
        unit_cost=custo,
        # Focus só é gasto no que se decide produzir.
        focus_per_unit=focus_unitario if escolhido is Sourcing.CRAFT else 0.0,
        steps=passos,
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
