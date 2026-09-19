"""Lista de compras: quanto comprar para produzir uma quantidade.

A conta **não** é `quantidade × receita`. O retorno de material volta para o
inventário e é reaproveitado na execução seguinte, então o consumo efetivo é:

    consumo = quantidade × receita × (1 − retorno)

Com 36,7% de retorno, produzir 100 unidades de couro T8 consome
`5 × 100 × 0,633 = 317` pelegos, não 500. É a mesma redução que o custo já
aplica desde a fase 7 — a lista de compras só a torna visível, em unidades em
vez de prata.

## Duas regras que a aritmética sozinha erra

**Arredonda para cima.** Não se compra 316,5 pelegos. Arredondar para baixo
faria a última execução faltar material, que é o pior jeito de descobrir o
erro — no meio da produção, com a estação ocupada.

**O retorno é uma promessa, não um fato.** Ele só se realiza para quem refina
tudo em sequência: o material que volta na execução `n` é o que alimenta a
`n+1`. Quem faz uma leva e para não recupera nada da última, e quem compra
exatamente a lista fica sem material antes do fim se parar no meio. A resposta
carrega essa ressalva em uma linha — é informação, não alarme.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ShoppingLine:
    """Quanto comprar de um material, e a conta por trás."""

    item: str
    per_unit: float
    """Quantidade que a receita pede por unidade produzida."""

    gross: float
    """`quantidade × receita`, antes do retorno."""

    units: int
    """O que de fato se compra: já com retorno e arredondado para cima."""

    saved: float
    """Quantas unidades o retorno poupou. É o valor da promessa."""


RESSALVA_DO_RETORNO = (
    "O retorno só se realiza refinando em sequência: o material que volta numa "
    "execução alimenta a seguinte. Quem faz uma leva e para não recupera o da "
    "última."
)


def effective_units(quantity: int, per_unit: float, return_rate: float | None) -> int:
    """Unidades a comprar de um material.

    `return_rate` em `None` significa retorno desconhecido — e aí **não se
    aplica desconto nenhum**. Supor retorno zero compraria material a mais, que
    é o lado seguro; supor o retorno cheio deixaria a produção parada no meio.
    """
    if quantity <= 0 or per_unit <= 0:
        return 0

    taxa = 0.0 if return_rate is None else max(0.0, min(1.0, return_rate))
    return math.ceil(quantity * per_unit * (1 - taxa))


def shopping_line(
    item: str, quantity: int, per_unit: float, return_rate: float | None
) -> ShoppingLine:
    bruto = max(0.0, quantity * per_unit)
    unidades = effective_units(quantity, per_unit, return_rate)
    return ShoppingLine(
        item=item,
        per_unit=per_unit,
        gross=round(bruto, 2),
        units=unidades,
        saved=round(max(0.0, bruto - unidades), 2),
    )
