"""Especialização: quanto ela reduz o custo em Focus.

Até a fase 15 o custo em Focus vinha cru do dump (`@craftingfocus`), que é o
custo de quem **nunca** especializou nada. Isso não é um detalhe de precisão: é
o que separa a conta de quem joga a sério da conta de quem não joga. Um refino
T4 custa 54 de Focus sem spec e 3 com tudo maximizado — dezoito vezes mais
refino no mesmo dia de Focus.

## A fórmula

    eficiencia = nivel_spec × fce_por_nivel + (mastery + mastery2) × 30
    focus      = focus_base × 0,5 ^ (eficiencia ÷ 10.000)

Cada 10.000 pontos de *focus cost efficiency* cortam o custo pela metade. Cada
nível de especialização do item vale 250 pontos "únicos" mais 30 "mútuos" para
os irmãos do mesmo nó; cada nível de maestria vale 30 pontos em toda a
categoria.

## Conferência

O dump diz `@craftingfocus = 54` para `T4_LEATHER`, que é exatamente o "54 sem
spec" que a comunidade reporta. E o teto reportado para refino T4–T8 é 40.000
de eficiência, que sai de `100 × 250` (spec do item) mais `5 × 100 × 30`
(maestria dos cinco tiers) — e `0,5^4 = 6,25%`, ou seja `54 → 3,375`, que é o
"custa 3" reportado. Os três números fecham entre si, e há teste amarrando os
três.

## Por que `fce_por_nivel` varia por tipo de peça

BAG vale 310 e CAPE vale 370, não 250. O padrão é `250 + (irmãos × 30)`: o nó
dá 250 ao próprio item e 30 a cada irmão, então um nó com mais irmãos devolve
mais pontos por nível. Pelo mesmo motivo a mão secundária vale 90 quando o spec
é de outra peça: aí só entram os 30 mútuos, três vezes, e não os 250 únicos.

## Spec ausente é zero, e isso é de propósito

Diferente de taxa ausente, que vira `UNKNOWN`. A regra aqui é a do risco de rota
(fase 13): **zero significa "não estou modelando especialização"**, o custo sai
idêntico ao do dump, e a tela diz que a conta assume spec 0. Travar a tela por
um número que só o usuário tem esconderia o produto de quem ainda não
configurou.
"""

from dataclasses import dataclass

# Cada 10.000 pontos de eficiência cortam o custo pela metade.
FOCUS_HALVING_EFFICIENCY = 10_000.0

# Maestria vale 30 pontos por nível, em toda a categoria.
FCE_PER_MASTERY_LEVEL = 30.0

# Teto de nível que o jogo aceita, tanto em spec quanto em maestria.
MAX_LEVEL = 100

FONTE = (
    "wiki oficial (Specializations, Crafting Focus) + planilha do Albion VIP; "
    "consultado em 19/09/2026; conferido contra @craftingfocus do dump; nao "
    "auditado contra codigo da Sandbox"
)


@dataclass(frozen=True)
class SpecProfile:
    """O que o usuário informa, por família.

    `fce_per_spec_level` muda com o tipo de peça e vem da configuração, não
    daqui: é dado, não fórmula.
    """

    spec_level: int = 0
    mastery_level: int = 0
    mastery2_level: int = 0
    fce_per_spec_level: float = 250.0

    @property
    def informed(self) -> bool:
        """Se o usuário mexeu em alguma coisa. Só serve para a tela avisar."""
        return bool(self.spec_level or self.mastery_level or self.mastery2_level)


@dataclass(frozen=True)
class FocusCost:
    """Custo em Focus depois da especialização, e como se chegou nele."""

    focus: float
    base_focus: float
    efficiency: float
    multiplier: float
    """`0,5 ^ (eficiencia ÷ 10.000)`. 1,0 quando não há especialização."""

    assumes_zero_spec: bool = False
    """True quando o usuário não informou spec. A tela precisa dizer isto."""


def _clamp_level(level: int) -> int:
    return max(0, min(MAX_LEVEL, int(level)))


def focus_efficiency(profile: SpecProfile) -> float:
    """Pontos de eficiência de um perfil.

    Níveis são limitados a 0–100 porque é o que o jogo aceita; um 999 digitado
    no formulário não pode virar Focus negativo nem custo zero.
    """
    spec = _clamp_level(profile.spec_level) * max(0.0, profile.fce_per_spec_level)
    mastery = (
        _clamp_level(profile.mastery_level) + _clamp_level(profile.mastery2_level)
    ) * FCE_PER_MASTERY_LEVEL
    return spec + mastery


def focus_cost_with_spec(base_focus: float, profile: SpecProfile) -> FocusCost:
    """Custo em Focus de uma execução, dada a especialização do usuário.

    `base_focus` é o `@craftingfocus` do dump — o custo de quem não especializou
    nada. Sem perfil informado a função devolve o próprio `base_focus`, com
    `assumes_zero_spec=True` para a tela poder dizê-lo.
    """
    base = max(0.0, float(base_focus))
    eficiencia = focus_efficiency(profile)
    multiplicador = 0.5 ** (eficiencia / FOCUS_HALVING_EFFICIENCY)

    return FocusCost(
        focus=round(base * multiplicador, 4),
        base_focus=base,
        efficiency=round(eficiencia, 2),
        multiplier=round(multiplicador, 6),
        assumes_zero_spec=not profile.informed,
    )
