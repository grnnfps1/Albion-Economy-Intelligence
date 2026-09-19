"""Política da especialização: qual nível vale para qual item.

`calculations/specialization.py` tem a fórmula. Aqui fica o que ela não pode
saber: quantos pontos de eficiência cada tipo de peça dá por nível (dado de
configuração) e qual família de recurso um `unique_name` pertence.

A granularidade é **por família**, não por item. A planilha do Albion VIP faz
item a item, mas isso são centenas de campos no formulário para uma decisão que
quase ninguém toma item a item: quem especializa couro especializa a linha
inteira. Cinco famílias cobrem o refino todo.

Craft de equipamento fica de fora por enquanto: a tabela de pontos por tipo de
peça está gravada com procedência (`crafting.focus_efficiency.per_spec_level`),
mas nenhuma preferência a alimenta ainda, então o craft calcula com spec 0 —
que é o lado conservador de errar, porque superestima o Focus gasto.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.specialization import (
    FCE_PER_MASTERY_LEVEL,
    FOCUS_HALVING_EFFICIENCY,
    FocusCost,
    SpecProfile,
    focus_cost_with_spec,
)
from app.repositories import settings_repo

FCE_PER_SPEC_KEY = "crafting.focus_efficiency.per_spec_level"
FAMILIES_KEY = "crafting.spec_families"

# `T5_PLANKS_LEVEL2@2` -> `PLANKS`. Mesmo formato que o refino já usa.
_FAMILIA = re.compile(r"^T\d_([A-Z]+?)(?:_LEVEL\d+)?(?:@\d)?$")

# Quando a configuração não trouxer a tabela, o refino vale 250 — é o valor de
# todas as linhas de recurso, e o único que a interface expõe.
DEFAULT_REFINING_FCE = 250.0

# As cinco linhas de recurso. Fonte única: a rota importa daqui em vez de
# repetir a lista, e a configuração pode sobrescrever.
#
# Por que existe um padrão em vez de exigir a configuração: sem ele, um banco
# sem a 0009 aplicada aceitaria o spec que o usuário informou e o ignoraria em
# silêncio — o pior dos dois mundos, porque a tela diria "spec 60" e a conta
# usaria zero.
DEFAULT_FAMILIES = ("LEATHER", "CLOTH", "PLANKS", "METALBAR", "STONEBLOCK")


def family_of(unique_name: str) -> str | None:
    match = _FAMILIA.match(unique_name)
    return match.group(1) if match else None


@dataclass(frozen=True)
class SpecializationPolicy:
    """Níveis informados por família, já prontos para virar custo de Focus."""

    levels: dict[str, int] = field(default_factory=dict)
    """`LEATHER -> 60`. Família ausente significa nível zero."""

    mastery_levels: dict[str, int] = field(default_factory=dict)
    mastery2_levels: dict[str, int] = field(default_factory=dict)
    fce_per_spec_level: dict[str, float] = field(default_factory=dict)
    families: tuple[str, ...] = DEFAULT_FAMILIES

    @property
    def informed(self) -> bool:
        """Se o usuário informou spec em alguma família."""
        return any(self.levels.values()) or any(self.mastery_levels.values())

    def profile_of(self, unique_name: str) -> SpecProfile:
        familia = family_of(unique_name)
        if familia is None or familia not in self.families:
            # Item fora das famílias mapeadas (craft de equipamento, por ora).
            # Spec 0: superestima o Focus, que é o lado seguro.
            return SpecProfile(fce_per_spec_level=self._fce("REFINING"))

        return SpecProfile(
            spec_level=self.levels.get(familia, 0),
            mastery_level=self.mastery_levels.get(familia, 0),
            mastery2_level=self.mastery2_levels.get(familia, 0),
            fce_per_spec_level=self._fce("REFINING"),
        )

    def focus_cost_of(self, unique_name: str, base_focus: float) -> FocusCost:
        return focus_cost_with_spec(base_focus, self.profile_of(unique_name))

    def _fce(self, tipo: str) -> float:
        valor = self.fce_per_spec_level.get(tipo)
        return DEFAULT_REFINING_FCE if valor is None else float(valor)


async def load_specialization_policy(
    session: AsyncSession,
    levels: dict[str, int] | None = None,
    mastery_levels: dict[str, int] | None = None,
    mastery2_levels: dict[str, int] | None = None,
) -> SpecializationPolicy:
    """Monta a política a partir da configuração e do que o usuário informou.

    Os níveis são do usuário e chegam da requisição; a tabela de pontos por
    tipo de peça e a lista de famílias são configuração com procedência.
    """
    config = await settings_repo.get_values(session, [FCE_PER_SPEC_KEY, FAMILIES_KEY])
    tabela = config.get(FCE_PER_SPEC_KEY) or {}
    familias = tuple(config.get(FAMILIES_KEY) or DEFAULT_FAMILIES)

    return SpecializationPolicy(
        levels={k.upper(): v for k, v in (levels or {}).items()},
        mastery_levels={k.upper(): v for k, v in (mastery_levels or {}).items()},
        mastery2_levels={k.upper(): v for k, v in (mastery2_levels or {}).items()},
        fce_per_spec_level={k: float(v) for k, v in tabela.items()},
        families=familias,
    )


def spec_out(policy: SpecializationPolicy) -> dict:
    """O que vai na resposta para a tela poder explicar o número.

    `assumes_zero_spec` existe porque "custa 54 de Focus" sem dizer que assume
    spec 0 é um número que parece medido.
    """
    return {
        "informed": policy.informed,
        "assumes_zero_spec": not policy.informed,
        "levels": dict(policy.levels),
        "families": list(policy.families),
        "halving_points": FOCUS_HALVING_EFFICIENCY,
        "per_mastery_level": FCE_PER_MASTERY_LEVEL,
        "per_spec_level": dict(policy.fce_per_spec_level),
    }
