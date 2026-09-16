"""Taxa de retorno de material: a célula certa da matriz.

Função pura, como o resto de `calculations/`. O retorno deixou de ser um número
único e virou uma matriz de quatro células por atividade:

                      | sem Focus | com Focus
    cidade com bônus  |   0,367   |   0,539     (refino)
    sem bônus         |   0,152   |   0,435

Duas coisas que a matriz resolve e um valor único não resolvia:

- **A cidade importa mais que o Focus, em refino.** Sair de 0,152 para 0,367 só
  mudando de cidade é mais do que o Focus dá sozinho (0,152 → 0,435 é maior,
  mas custa o recurso escasso). Com um valor único, essa decisão era invisível.
- **Craft e refino têm bônus diferentes.** O de refino segue o recurso; o de
  craft segue a família do item. Usar a mesma taxa para os dois errava um deles
  sempre.

`None` em qualquer célula continua significando UNKNOWN, e o cálculo que
depender dela devolve UNKNOWN em vez de zero — a regra não mudou.
"""

from dataclasses import dataclass
from enum import StrEnum


class Activity(StrEnum):
    CRAFTING = "CRAFT"
    REFINING = "REFINO"


@dataclass(frozen=True)
class ReturnMatrix:
    """As quatro células de uma atividade. `None` é UNKNOWN, nunca zero."""

    bonus_base: float | None = None
    bonus_focus: float | None = None
    base: float | None = None
    focus: float | None = None

    def cell(self, has_city_bonus: bool, use_focus: bool) -> float | None:
        if has_city_bonus:
            return self.bonus_focus if use_focus else self.bonus_base
        return self.focus if use_focus else self.base

    @property
    def complete(self) -> bool:
        return all(
            valor is not None
            for valor in (self.bonus_base, self.bonus_focus, self.base, self.focus)
        )


@dataclass(frozen=True)
class ReturnResolution:
    """A taxa em uso, e tudo que permite auditá-la.

    `rate` sozinho não diz se veio da cidade certa, se o Focus entrou ou se o
    usuário sobrescreveu. Sem isso, um retorno de 53,9% não é conferível.
    """

    rate: float | None
    source: str
    """'matriz', 'preferencia' ou 'UNKNOWN'."""

    has_city_bonus: bool = False
    use_focus: bool = False
    daily_bonus: float = 0.0
    matrix_rate: float | None = None
    """A célula da matriz antes do bônus diário e antes de qualquer sobrescrita."""

    @property
    def known(self) -> bool:
        return self.rate is not None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def resolve_return_rate(
    matrix: ReturnMatrix,
    has_city_bonus: bool,
    use_focus: bool,
    daily_bonus: float = 0.0,
    override: float | None = None,
) -> ReturnResolution:
    """Taxa de retorno em uso.

    Precedência, **invertida** em relação às taxas de mercado: aqui a matriz é o
    valor primário e a preferência do usuário é sobrescrita opcional. O motivo é
    que a matriz tem procedência e depende de (cidade, atividade, Focus), coisas
    que o sistema sabe; o usuário só precisa intervir quando a situação dele é
    atípica — especialização alta, por exemplo.

    O bônus diário de produção entra **somado** à célula. O jogo sorteia 0, 10%
    ou 20% por dia; como ele não foi medido junto com a matriz, a soma é a
    leitura mais simples e vai declarada como suposição na resposta.
    """
    celula = matrix.cell(has_city_bonus, use_focus)
    diario = _clamp(daily_bonus)

    if override is not None:
        return ReturnResolution(
            rate=_clamp(override + diario),
            source="preferencia",
            has_city_bonus=has_city_bonus,
            use_focus=use_focus,
            daily_bonus=diario,
            matrix_rate=celula,
        )

    if celula is None:
        return ReturnResolution(
            rate=None,
            source="UNKNOWN",
            has_city_bonus=has_city_bonus,
            use_focus=use_focus,
            daily_bonus=diario,
        )

    return ReturnResolution(
        rate=_clamp(celula + diario),
        source="matriz",
        has_city_bonus=has_city_bonus,
        use_focus=use_focus,
        daily_bonus=diario,
        matrix_rate=celula,
    )
