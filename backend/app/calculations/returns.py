"""Taxa de retorno de material: a fórmula, não uma tabela de valores.

Até a fase 19 isto era uma matriz de quatro células por atividade, com valores
medidos pela comunidade. A fase 20 substitui a tabela pela **fórmula que a
gera**:

    B   = soma dos bônus aplicáveis
    RRR = B ÷ (1 + B)

Os bônus são os oficiais, e se somam antes da conversão:

| Componente | Valor | Quando entra |
|---|---|---|
| base de cidade | +18% | sempre, **exceto em ilha** |
| refino da cidade | +40% | refinando na cidade do recurso |
| craft da cidade | +15% | craftando na cidade da família do item |
| foco | +59% | com Focus |

## Por que isto resolve uma contradição, e não cria outra

O item 6 de `docs/04-taxas.md` vivia num impasse aparente: a documentação
oficial fala em **+40% de bônus** e a comunidade mede **36,7% de retorno**. Os
dois estavam certos e mediam coisas diferentes — `0,58 ÷ 1,58 = 0,367`. O bônus
é o que a estação soma; o retorno é a fração das unidades que volta. A fórmula é
a conversão entre os dois, e é por isso que o número da comunidade tem decimal.

## Conferência

Os quatro componentes reproduzem os valores medidos:

| Cenário | B | RRR | Medido |
|---|---|---|---|
| refino, sem bônus de cidade, sem foco | 0,18 | 0,1525 | 0,152 |
| refino, com bônus, sem foco | 0,58 | 0,3671 | 0,367 |
| refino, sem bônus, com foco | 0,77 | 0,4350 | 0,435 |
| refino, com bônus, com foco | 1,17 | 0,5392 | 0,539 |
| craft, com bônus, sem foco | 0,33 | 0,2481 | 0,248 |
| ilha, sem foco | 0,00 | 0,0000 | 0 |
| ilha, com foco | 0,59 | 0,3711 | 0,371 |

**Uma célula não fechou**, e a fórmula ganhou: craft com bônus de cidade **e**
foco dá `0,92 ÷ 1,92 = 0,4792`, contra os `0,477` que a fase 14 havia gravado.
O desvio é de 0,0022 — dez vezes maior que o de qualquer outra célula, todas
abaixo de 0,0006. É o valor tabelado que estava impreciso, não a fórmula.

## O bônus diário é o quinto componente, e vem do usuário

O jogo sorteia um bônus diário de produção, e ele entra **em `B`**, somado aos
outros quatro — não no `RRR` já convertido. Foi essa a confusão que fez as
tabelas publicadas não fecharem quando se tentou somá-lo ao resultado: somar
percentual de retorno a percentual de retorno é a mesma categoria de erro que
somar `0,152 + 0,367` esperando `0,519`.

Ele **não** é constante do jogo: varia por cidade e por dia, e o sistema não tem
como sabê-lo. Por isso é entrada do usuário, que o lê na tela — mesmo perfil da
prata por 100 de nutrição.

O padrão é **zero**, e a resposta carrega `assumes_no_daily_bonus`. É o
precedente do spec (fase 16) e do risco de rota (fase 13): zero aqui significa
"não estou modelando o bônus", o retorno sai igual ao da fórmula sem ele, e a
tela diz isso — em vez de travar por um número que só o jogador tem.
"""

from dataclasses import dataclass
from enum import StrEnum


class Activity(StrEnum):
    CRAFTING = "CRAFT"
    REFINING = "REFINO"


@dataclass(frozen=True)
class ReturnComponents:
    """Os bônus que compõem `B`. `None` em qualquer um é UNKNOWN, nunca zero."""

    city_base: float | None = None
    refining_city: float | None = None
    crafting_city: float | None = None
    focus: float | None = None

    @property
    def complete(self) -> bool:
        return all(
            v is not None
            for v in (self.city_base, self.refining_city, self.crafting_city, self.focus)
        )

    def missing(self) -> list[str]:
        faltando = []
        for nome, valor in (
            ("crafting.return_bonus.city_base", self.city_base),
            ("refining.return_bonus.city", self.refining_city),
            ("crafting.return_bonus.city", self.crafting_city),
            ("crafting.return_bonus.focus", self.focus),
        ):
            if valor is None:
                faltando.append(nome)
        return faltando


@dataclass(frozen=True)
class ReturnResolution:
    """A taxa em uso, e tudo que permite auditá-la.

    `rate` sozinho não diz se veio da cidade certa, se o Focus entrou ou se o
    usuário sobrescreveu. Sem isso, um retorno de 53,9% não é conferível.
    """

    rate: float | None
    source: str
    """'formula', 'preferencia' ou 'UNKNOWN'."""

    has_city_bonus: bool = False
    use_focus: bool = False
    is_island: bool = False
    daily_bonus: float = 0.0
    assumes_no_daily_bonus: bool = True
    """True quando o usuário não informou o bônus do dia. A tela precisa dizê-lo."""

    bonus_total: float | None = None
    """O `B` da fórmula — a soma dos bônus, antes da conversão."""

    formula_rate: float | None = None
    """A taxa pela fórmula, antes de qualquer sobrescrita."""

    @property
    def known(self) -> bool:
        return self.rate is not None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def rrr_from_bonus(bonus_total: float) -> float:
    """`B ÷ (1 + B)`.

    A conversão de "quanto a estação soma" para "que fração das unidades
    volta". Nunca passa de 1 por construção, mesmo com bônus absurdo — é a
    propriedade que torna a fórmula segura contra entrada estranha.
    """
    b = max(0.0, bonus_total)
    return b / (1 + b)


def total_bonus(
    components: ReturnComponents,
    activity: Activity,
    has_city_bonus: bool,
    use_focus: bool,
    is_island: bool = False,
    daily_bonus: float = 0.0,
) -> float | None:
    """`B`: a soma dos bônus aplicáveis. `None` quando falta componente.

    `daily_bonus` entra aqui, junto dos outros — e não sobre o `RRR` depois.
    """
    if not components.complete:
        return None

    # Ilha não tem a base de cidade — é o que faz quem refina em ilha ter 0% de
    # retorno sem Focus, e 37,1% com.
    total = 0.0 if is_island else (components.city_base or 0.0)

    if has_city_bonus:
        total += (
            components.refining_city if activity is Activity.REFINING
            else components.crafting_city
        ) or 0.0

    if use_focus:
        total += components.focus or 0.0

    # O bônus do dia soma como qualquer outro componente.
    total += max(0.0, daily_bonus)

    return total


def resolve_return_rate(
    components: ReturnComponents,
    activity: Activity,
    has_city_bonus: bool,
    use_focus: bool,
    is_island: bool = False,
    daily_bonus: float = 0.0,
    override: float | None = None,
) -> ReturnResolution:
    """Taxa de retorno em uso.

    Precedência, **invertida** em relação às taxas de mercado: aqui a fórmula é
    o valor primário e a preferência do usuário é sobrescrita opcional. O motivo
    é que a fórmula depende de (cidade, atividade, Focus, ilha) — coisas que o
    sistema sabe — e o usuário só precisa intervir quando a situação dele é
    atípica.
    """
    b = total_bonus(
        components, activity, has_city_bonus, use_focus, is_island, daily_bonus
    )
    pela_formula = None if b is None else rrr_from_bonus(b)

    if override is not None:
        return ReturnResolution(
            rate=_clamp(override),
            source="preferencia",
            has_city_bonus=has_city_bonus,
            use_focus=use_focus,
            is_island=is_island,
            daily_bonus=daily_bonus,
            assumes_no_daily_bonus=daily_bonus <= 0,
            bonus_total=b,
            formula_rate=pela_formula,
        )

    if pela_formula is None:
        return ReturnResolution(
            rate=None,
            source="UNKNOWN",
            has_city_bonus=has_city_bonus,
            use_focus=use_focus,
            is_island=is_island,
            daily_bonus=daily_bonus,
            assumes_no_daily_bonus=daily_bonus <= 0,
        )

    return ReturnResolution(
        rate=pela_formula,
        source="formula",
        has_city_bonus=has_city_bonus,
        use_focus=use_focus,
        is_island=is_island,
        daily_bonus=daily_bonus,
        assumes_no_daily_bonus=daily_bonus <= 0,
        bonus_total=b,
        formula_rate=pela_formula,
    )
