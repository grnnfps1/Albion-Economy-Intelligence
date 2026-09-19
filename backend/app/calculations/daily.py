"""Lucro por dia: o que torna craft, refino e fazenda comparáveis.

`/farming` já normaliza por dia desde a fase 12, e é a única tela que fazia
isso. Sem o mesmo número em craft e refino, a pergunta que a ferramenta deveria
responder — *coloco a parcela para plantar ou refino couro hoje?* — não tinha
resposta: os dois lados estavam em unidades diferentes.

## Por que não sai do tempo de craft

A ideia óbvia é dividir o lucro pelo tempo de produção, como a fazenda faz com
o ciclo. **Não funciona, por dois motivos, e o segundo é o que decide.**

**Primeiro: o dump não sustenta o número.** `craftingrequirements.@time` existe,
mas a unidade não é determinável a partir do arquivo. Conferido em 19/09/2026:

- vai de `0.0` a `10.0`, e **768 itens têm `0.0`** — entre eles todas as
  sementes de fazenda;
- não é proporcional ao Focus: em couro, `@craftingfocus ÷ @time` vai de 864 no
  T2 a 3.219 no T8;
- `T8_LEATHER` tem `@time = 0,15625`. Lido como segundos dá 553 mil unidades por
  dia; como minutos, 9.216; como horas, 6,4. **Três ordens de grandeza**, e nada
  no dump desempata.

Dividir por um número cujo expoente eu teria que arbitrar é inventar a resposta
— é a regra 2, e é a regra 12 recém-aprendida.

**Segundo, e mais importante: craft não é limitado por tempo.** Não há fila de
produção no Albion. Quem tem material e prata crafta mil itens num minuto. O que
limita a produção de um dia é o **Focus**, que regenera devagar, e o que o
**mercado absorve**. Mesmo que `@time` fosse confiável, dividir por ele
responderia uma pergunta que ninguém faz.

Fazenda é diferente *de verdade*: um ciclo leva 22 horas e não há como
apressá-lo. Ali o tempo é o limite, e por isso lá a conta é por ciclo.

## O que a conta é

    unidades no dia = min(focus_do_dia ÷ focus_por_unidade, giro_diário)
    lucro por dia   = lucro_por_unidade × unidades_no_dia

E o **limitador vai junto**, porque saber se a trava é o Focus ou o mercado muda
a decisão: adianta subir spec ou adianta procurar outro item? É a mesma lição da
fase 9, aplicada a outra tela.
"""

from dataclasses import dataclass
from enum import StrEnum


class DailyLimiter(StrEnum):
    FOCUS = "FOCUS"
    """O Focus do dia acaba antes de o mercado saturar."""

    MARKET = "MERCADO"
    """O mercado satura antes de o Focus acabar."""

    UNKNOWN = "DESCONHECIDO"
    """Sem giro medido: não dá para saber quanto o mercado absorve."""


@dataclass(frozen=True)
class DailyYield:
    """Quanto uma operação rende num dia, e o que a trava."""

    profit: float | None
    """`None` é UNKNOWN, nunca zero — sem giro e sem Focus não há teto."""

    units: float | None = None
    limiter: DailyLimiter = DailyLimiter.UNKNOWN
    units_by_focus: float | None = None
    units_by_market: float | None = None
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.profit is not None


def daily_yield(
    unit_profit: float | None,
    focus_per_unit: float,
    focus_per_day: float | None,
    market_units_per_day: float | None,
) -> DailyYield:
    """Lucro de um dia desta operação.

    `focus_per_unit` em zero significa que a operação não gasta Focus — aí o
    único teto é o mercado. Se o mercado também for desconhecido, o resultado é
    `UNKNOWN`: sem nenhum teto, "por dia" não tem resposta, e devolver o lucro
    unitário como se fosse diário seria mentir por um fator arbitrário.
    """
    if unit_profit is None:
        return DailyYield(profit=None, reason="lucro unitário desconhecido")

    por_focus: float | None = None
    if focus_per_unit > 0:
        if focus_per_day is None or focus_per_day <= 0:
            return DailyYield(
                profit=None,
                reason="sem orçamento diário de Focus para uma operação que gasta Focus",
            )
        por_focus = focus_per_day / focus_per_unit

    por_mercado = (
        market_units_per_day
        if market_units_per_day is not None and market_units_per_day > 0
        else None
    )

    if por_focus is None and por_mercado is None:
        return DailyYield(
            profit=None,
            reason="sem giro medido e sem custo de Focus: nada limita o dia",
            units_by_focus=por_focus,
            units_by_market=por_mercado,
        )

    candidatos = [v for v in (por_focus, por_mercado) if v is not None]
    unidades = min(candidatos)

    # O limitador é quem define a decisão seguinte: Focus pede spec, mercado
    # pede outro item. Empate conta como mercado — é o teto que não se muda
    # com investimento pessoal.
    if por_mercado is not None and unidades == por_mercado:
        limitador = DailyLimiter.MARKET
    elif por_focus is not None:
        limitador = DailyLimiter.FOCUS
    else:
        limitador = DailyLimiter.UNKNOWN

    return DailyYield(
        profit=round(unit_profit * unidades, 2),
        units=round(unidades, 2),
        limiter=limitador,
        units_by_focus=None if por_focus is None else round(por_focus, 2),
        units_by_market=None if por_mercado is None else round(por_mercado, 2),
    )
