"""Ranking de Focus.

Prata por Focus é uma **taxa**, não um ganho. Ela responde "quanto rende cada
ponto de Focus", e ordenar só por ela leva a uma recomendação que não se executa:

- Focus tem teto. Você não gasta o que não tem.
- O mercado tem teto. Escoar 5.000 unidades de algo que gira 3 por dia leva
  quatro anos, e a margem evapora muito antes disso.

Por isso o ranking cruza a taxa com dois limites e devolve o **ganho realizável**
no horizonte escolhido. Uma operação com prata/Focus menor mas que escoa pode
render mais na prática — e é isso que o jogador precisa ver.

Funções puras: entram números, saem números.
"""

from dataclasses import dataclass
from enum import StrEnum


class Route(StrEnum):
    CRAFT = "CRAFTING"
    REFINE = "REFINO"


class Limiter(StrEnum):
    FOCUS = "FOCUS"
    """O teto é o Focus disponível: dá para vender mais do que dá para produzir."""

    LIQUIDITY = "LIQUIDEZ"
    """O teto é o mercado: dá para produzir mais do que dá para escoar."""

    UNKNOWN = "DESCONHECIDO"
    """Liquidez desconhecida — não dá para dizer qual limite manda."""


@dataclass(frozen=True)
class FocusCandidate:
    item: str
    route: Route
    profit_per_unit: float
    focus_per_unit: float
    liquidity_units_per_day: float | None


@dataclass(frozen=True)
class FocusPlan:
    item: str
    route: Route
    profit_per_unit: float
    focus_per_unit: float
    profit_per_focus: float | None
    units_by_focus: float | None
    units_by_liquidity: float | None
    units: float | None
    focus_used: float | None
    realizable_profit: float | None
    limiter: Limiter
    days_to_sell: float | None


def plan_for(
    candidate: FocusCandidate, focus_budget: float | None, horizon_days: int
) -> FocusPlan:
    """Quanto essa operação rende de verdade dentro dos dois tetos."""
    taxa = (
        candidate.profit_per_unit / candidate.focus_per_unit
        if candidate.focus_per_unit > 0
        else None
    )

    por_focus = (
        focus_budget / candidate.focus_per_unit
        if focus_budget is not None and candidate.focus_per_unit > 0
        else None
    )
    por_liquidez = (
        candidate.liquidity_units_per_day * horizon_days
        if candidate.liquidity_units_per_day is not None
        else None
    )

    if por_focus is None and por_liquidez is None:
        unidades, limitador = None, Limiter.UNKNOWN
    elif por_liquidez is None:
        # Sem saber o giro, o único teto conhecido é o Focus -- mas o limitador
        # fica UNKNOWN, porque o mercado pode ser o gargalo real.
        unidades, limitador = por_focus, Limiter.UNKNOWN
    elif por_focus is None:
        unidades, limitador = por_liquidez, Limiter.LIQUIDITY
    else:
        unidades = min(por_focus, por_liquidez)
        limitador = Limiter.FOCUS if por_focus <= por_liquidez else Limiter.LIQUIDITY

    ganho = None if unidades is None else unidades * candidate.profit_per_unit
    focus_usado = None if unidades is None else unidades * candidate.focus_per_unit
    dias = (
        unidades / candidate.liquidity_units_per_day
        if unidades is not None
        and candidate.liquidity_units_per_day
        and candidate.liquidity_units_per_day > 0
        else None
    )

    return FocusPlan(
        item=candidate.item,
        route=candidate.route,
        profit_per_unit=round(candidate.profit_per_unit, 2),
        focus_per_unit=round(candidate.focus_per_unit, 2),
        profit_per_focus=round(taxa, 2) if taxa is not None else None,
        units_by_focus=round(por_focus, 1) if por_focus is not None else None,
        units_by_liquidity=round(por_liquidez, 1) if por_liquidez is not None else None,
        units=round(unidades, 1) if unidades is not None else None,
        focus_used=round(focus_usado, 1) if focus_usado is not None else None,
        realizable_profit=round(ganho, 2) if ganho is not None else None,
        limiter=limitador,
        days_to_sell=round(dias, 1) if dias is not None else None,
    )


def build_ranking(
    candidates: list[FocusCandidate],
    focus_budget: float | None,
    horizon_days: int = 7,
    sort_by: str = "realizable_profit",
    sort_desc: bool = True,
) -> list[FocusPlan]:
    """Ordena e deduplica.

    Um mesmo item pode aparecer por dois caminhos — craft direto e refino. Manter
    os dois na lista ocuparia duas linhas com a mesma decisão; fica o melhor, e a
    rota escolhida aparece na linha.
    """
    planos = [plan_for(candidate, focus_budget, horizon_days) for candidate in candidates]

    def bruto(plano: FocusPlan) -> float | None:
        if sort_by == "profit_per_focus":
            return plano.profit_per_focus
        return plano.realizable_profit

    def valor(plano: FocusPlan) -> float:
        """Só para a deduplicação: entre dois caminhos, fica o de maior valor.

        Aqui o desconhecido tem de perder sempre, e por isso vira `-1e18` — é
        escolha de qual linha manter, não posição no ranking.
        """
        v = bruto(plano)
        return v if v is not None else -1e18

    melhores: dict[str, FocusPlan] = {}
    for plano in planos:
        atual = melhores.get(plano.item)
        if atual is None or valor(plano) > valor(atual):
            melhores[plano.item] = plano

    def ordem(plano: FocusPlan):
        """Desconhecido no fim, nas duas direções.

        A separação entra **antes** do valor na tupla e o sinal entra no valor.
        Com `reverse`, a inversão pegaria também a separação e as linhas sem
        cálculo subiriam ao topo no crescente. Mesma regra do calculador e de
        `/crafting`.
        """
        v = bruto(plano)
        return (v is None, -(v or 0.0) if sort_desc else (v or 0.0))

    return sorted(melhores.values(), key=ordem)
