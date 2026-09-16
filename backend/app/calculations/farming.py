"""Economia de um ciclo de fazenda, horta, pasto ou canil.

Funções puras. Como no resto de `calculations/`, todo parâmetro de jogo chega
como argumento e ausência vira `UNKNOWN` — nunca zero.

**O ponto desta fase é o tempo.** Um ciclo de fazenda leva 22 horas; um filhote
de montaria T8 leva quase um mês. "Lucro por ciclo" compara coisas que não são
comparáveis, e "lucro por craft" ao lado de "lucro por colheita" é pior ainda.
Tudo aqui sai normalizado em **prata por dia** e **prata por Focus** — as duas
únicas medidas que põem uma cenoura e uma barra de aço na mesma régua.

E as duas medem coisas diferentes, de propósito:

- prata **por dia** responde "quanto rende o terreno que eu tenho";
- prata **por Focus** responde "quanto rende o Focus que eu tenho".

Quem tem parcela sobrando e Focus curto decide por uma; quem tem Focus sobrando
e parcela cheia decide pela outra.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.calculations.fees import FeeProfile, Strategy, compute_trade

DAY_SECONDS = 86_400


class PlanKind(StrEnum):
    CROP = "CULTIVO"
    """Semente → colheita. Um ciclo, 22 horas."""

    BREEDING = "CRIACAO"
    """Filhote → adulto, consumindo ração. É cadeia: a ração vem da fazenda."""

    PRODUCT = "PRODUTO"
    """Adulto → leite ou ovo, a cada ciclo, sem consumir o adulto."""


@dataclass(frozen=True)
class FarmInput:
    """O que entra no ciclo: a semente, o filhote, a ração.

    `quantity` é `float` porque ração não é discreta: um filhote consome um
    ponto de nutrição a cada N segundos, e o total quase nunca é inteiro.
    Arredondar para cima aqui esconderia o custo real numa casa decimal.
    """

    unique_name: str
    display_name: str | None
    quantity: float
    unit_price: int | None
    location: str | None = None
    age_seconds: int | None = None

    @property
    def known(self) -> bool:
        return self.unit_price is not None

    @property
    def cost(self) -> float | None:
        return None if self.unit_price is None else self.unit_price * self.quantity


@dataclass(frozen=True)
class FarmOutput:
    """O que sai do ciclo.

    A quantidade é faixa (`3-6` cenouras) e pode ter chance menor que 1 (a cria
    que às vezes nasce). O valor esperado multiplica as duas coisas -- é a única
    leitura honesta de "quanto isso rende em média".

    `primary` separa o que o ciclo existe para produzir do que cai junto. Um
    cultivo sem cotação da colheita é desconhecido; o mesmo cultivo sem cotação
    da minhoca que cai a 10% continua conhecido, só que rendendo um pouco menos
    do que renderia. Subestimar é o lado certo de errar.
    """

    unique_name: str
    display_name: str | None
    amount_min: int
    amount_max: int
    chance: float
    unit_price: int | None
    primary: bool = True
    taxed: bool = True
    """A semente que volta não passa pelo mercado: ela é replantada. Cobrar
    imposto de venda sobre ela inventaria uma taxa que ninguém paga."""

    @property
    def known(self) -> bool:
        return self.unit_price is not None

    @property
    def expected_amount(self) -> float:
        return (self.amount_min + self.amount_max) / 2 * self.chance


@dataclass(frozen=True)
class FarmEconomics:
    known: bool
    reason: str | None = None
    kind: str = ""

    cycle_seconds: int = 0
    cycle_days: float = 0.0
    focus_cost: int = 0

    input_cost: float | None = None
    gross_revenue: float | None = None
    sale_revenue_net: float | None = None
    market_fees: float | None = None

    profit_per_cycle: float | None = None
    profit_per_day: float | None = None
    profit_per_focus: float | None = None
    focus_per_day: float | None = None

    margin_pct: float | None = None
    roi_pct: float | None = None

    # Saídas que existem mas não têm cotação: ficaram fora da receita, e o lucro
    # calculado está abaixo do real por causa delas.
    outputs_without_price: list[str] = field(default_factory=list)


def per_day(value: float | None, seconds: int) -> float | None:
    """Converte "por ciclo" em "por dia". É o que torna tudo comparável."""
    if value is None or seconds <= 0:
        return None
    return value / (seconds / DAY_SECONDS)


def _unknown(reason: str, kind: str, seconds: int, focus: int) -> FarmEconomics:
    return FarmEconomics(
        known=False,
        reason=reason,
        kind=kind,
        cycle_seconds=seconds,
        cycle_days=round(seconds / DAY_SECONDS, 4) if seconds > 0 else 0.0,
        focus_cost=focus,
    )


def compute_farm_cycle(
    kind: PlanKind,
    inputs: list[FarmInput],
    outputs: list[FarmOutput],
    fees: FeeProfile,
    cycle_seconds: int,
    focus_cost: int = 0,
    strategy: Strategy = Strategy.FAST,
) -> FarmEconomics:
    """Lucro de **um** ciclo, e o mesmo lucro normalizado por dia e por Focus."""
    tipo = str(kind)

    if cycle_seconds <= 0:
        return _unknown("duração do ciclo desconhecida", tipo, cycle_seconds, focus_cost)

    if not outputs:
        return _unknown("o dump não diz o que este ciclo entrega", tipo, cycle_seconds, focus_cost)

    sem_preco_entrada = [i.unique_name for i in inputs if not i.known]
    if sem_preco_entrada:
        # Custo parcial não é custo menor -- é custo desconhecido.
        return _unknown(
            f"sem cotação para {len(sem_preco_entrada)} insumo(s): "
            f"{', '.join(sem_preco_entrada[:3])}",
            tipo,
            cycle_seconds,
            focus_cost,
        )

    principais = [o for o in outputs if o.primary]
    if not principais:
        return _unknown("ciclo sem saída principal", tipo, cycle_seconds, focus_cost)

    sem_preco_principal = [o.unique_name for o in principais if not o.known]
    if sem_preco_principal:
        return _unknown(
            f"sem cotação de venda para {', '.join(sem_preco_principal[:3])}",
            tipo,
            cycle_seconds,
            focus_cost,
        )

    if not fees.complete:
        return _unknown(
            "taxas não configuradas: " + ", ".join(fees.missing()), tipo, cycle_seconds, focus_cost
        )

    custo = sum(entrada.cost or 0.0 for entrada in inputs)

    receita_bruta = 0.0
    receita_liquida = 0.0
    taxas = 0.0
    sem_cotacao: list[str] = []

    for saida in outputs:
        if not saida.known:
            sem_cotacao.append(saida.unique_name)
            continue
        unidades = saida.expected_amount
        if unidades <= 0:
            continue
        if saida.taxed:
            # `unit_revenue` é por unidade e não depende da quantidade, então a
            # operação é calculada uma vez e multiplicada pelo valor esperado --
            # que é fracionário e não caberia em `quantity`.
            operacao = compute_trade(
                buy_price=1,  # o custo entra por fora; só interessam as taxas de venda
                sell_price=saida.unit_price,
                fees=fees,
                strategy=strategy,
                quantity=1,
            )
            liquido = operacao.unit_revenue or 0.0
        else:
            liquido = float(saida.unit_price)

        receita_bruta += saida.unit_price * unidades
        receita_liquida += liquido * unidades
        taxas += (saida.unit_price - liquido) * unidades

    lucro = receita_liquida - custo

    return FarmEconomics(
        known=True,
        kind=tipo,
        cycle_seconds=cycle_seconds,
        cycle_days=round(cycle_seconds / DAY_SECONDS, 4),
        focus_cost=focus_cost,
        input_cost=round(custo, 2),
        gross_revenue=round(receita_bruta, 2),
        sale_revenue_net=round(receita_liquida, 2),
        market_fees=round(taxas, 2),
        profit_per_cycle=round(lucro, 2),
        # A conversão que dá sentido ao ranking: 22 horas e 28 dias não se
        # comparam por ciclo.
        profit_per_day=round(per_day(lucro, cycle_seconds) or 0.0, 2),
        profit_per_focus=round(lucro / focus_cost, 2) if focus_cost > 0 else None,
        focus_per_day=round(per_day(float(focus_cost), cycle_seconds) or 0.0, 2)
        if focus_cost > 0
        else None,
        margin_pct=round(lucro / receita_bruta * 100, 2) if receita_bruta else None,
        roi_pct=round(lucro / custo * 100, 2) if custo else None,
        outputs_without_price=sem_cotacao,
    )
