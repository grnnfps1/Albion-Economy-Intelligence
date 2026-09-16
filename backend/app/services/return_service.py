"""Onde o retorno de material é maior, e por quê.

`calculations/returns.py` escolhe a célula da matriz. Aqui fica a política:
**qual cidade tem o bônus** para aquele item, o que é dado de configuração e
não fórmula.

As duas atividades têm bônus em eixos diferentes, e é isso que a tela precisa
comunicar:

- **refino** segue o *recurso*, que segue o bioma da cidade: madeira em Fort
  Sterling, fibra em Lymhurst, pedra em Bridgewatch, couro em Martlock, minério
  em Thetford. Caerleon não tem bônus nos cinco básicos;
- **craft** segue a *família do item*, que é outra divisão inteiramente.

Os dois mapas nunca coincidem — conferido: em 9 de 9 peças de armadura, a
cidade que refina o material não é a que dá bônus para craftá-la. Isso não é
inconsistência: é o que obriga o material a viajar entre cidades.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.returns import Activity, ReturnMatrix, ReturnResolution, resolve_return_rate
from app.repositories import settings_repo
from app.schemas.crafting import ReturnOut

CRAFT_FAMILIES_KEY = "crafting.city_bonus_families"
REFINE_RESOURCES_KEY = "refining.city_bonus_resources"
UNMAPPED_KEY = "crafting.city_bonus_unmapped"

MATRIX_KEYS = {
    Activity.REFINING: (
        "refining.return_rate.bonus.base",
        "refining.return_rate.bonus.focus",
        "refining.return_rate.base",
        "refining.return_rate.focus",
    ),
    Activity.CRAFTING: (
        "crafting.return_rate.bonus.base",
        "crafting.return_rate.bonus.focus",
        "crafting.return_rate.base",
        "crafting.return_rate.focus",
    ),
}

# `T5_PLANKS_LEVEL2@2` -> `PLANKS`. O mesmo formato que o refino já usava.
_FAMILIA = re.compile(r"^T\d_([A-Z]+?)(?:_LEVEL\d+)?(?:@\d)?$")

# `T4_2H_BOW@1` -> `2H_BOW`. O tier sai porque o bônus é da família, não do tier.
_SEM_TIER = re.compile(r"^T\d_")


def family_of(unique_name: str) -> str | None:
    """Família de recurso: PLANKS, METALBAR, LEATHER, CLOTH, STONEBLOCK…"""
    match = _FAMILIA.match(unique_name)
    return match.group(1) if match else None


def base_token(unique_name: str) -> str:
    """O identificador sem o tier e sem o encantamento, para casar prefixo."""
    return _SEM_TIER.sub("", unique_name.split("@")[0])


@dataclass(frozen=True)
class CityBonus:
    """Onde aquele item rende mais, e quanto muda."""

    city_slug: str | None
    rate_here: float | None
    rate_there: float | None

    @property
    def known(self) -> bool:
        return self.city_slug is not None and self.rate_there is not None

    @property
    def is_here(self) -> bool:
        """A cidade em uso já é a do bônus?"""
        return self.city_slug is not None and self.rate_there == self.rate_here

    @property
    def delta(self) -> float | None:
        if self.rate_here is None or self.rate_there is None:
            return None
        return round(self.rate_there - self.rate_here, 4)


@dataclass
class ReturnPolicy:
    matrices: dict[Activity, ReturnMatrix]
    craft_families: dict[str, list[str]] = field(default_factory=dict)
    refine_resources: dict[str, list[str]] | None = None
    unmapped: dict[str, list[str]] = field(default_factory=dict)

    def bonus_city(self, activity: Activity, unique_name: str) -> str | None:
        """Cidade com bônus para este item, ou `None` quando não há mapa.

        `None` significa duas coisas diferentes e as duas terminam igual: ou o
        mapeamento não foi levantado, ou o item não casa com nenhuma família.
        Nos dois casos o item fica sem bônus, que é o lado conservador.
        """
        if activity is Activity.REFINING:
            if not self.refine_resources:
                return None
            familia = family_of(unique_name)
            if familia is None:
                return None
            for cidade, familias in self.refine_resources.items():
                if familia in familias:
                    return cidade
            return None

        token = base_token(unique_name)
        for cidade, prefixos in self.craft_families.items():
            if any(token.startswith(prefixo) for prefixo in prefixos):
                return cidade
        return None

    def resolve(
        self,
        activity: Activity,
        unique_name: str,
        city_slug: str,
        use_focus: bool,
        daily_bonus: float = 0.0,
        override: float | None = None,
    ) -> tuple[ReturnResolution, CityBonus]:
        """A taxa em uso e a cidade que renderia mais.

        A segunda parte é a pergunta que as telas deviam responder e não
        respondiam: *onde* refinar ou craftar isto rende mais, e quanto muda.
        """
        matriz = self.matrices.get(activity, ReturnMatrix())
        cidade_bonus = self.bonus_city(activity, unique_name)
        tem_bonus = cidade_bonus is not None and cidade_bonus == city_slug

        atual = resolve_return_rate(matriz, tem_bonus, use_focus, daily_bonus, override)

        # Quanto renderia na cidade do bônus, com os mesmos parâmetros.
        if cidade_bonus is None:
            melhor = CityBonus(None, atual.rate, None)
        else:
            la = resolve_return_rate(matriz, True, use_focus, daily_bonus, override)
            melhor = CityBonus(cidade_bonus, atual.rate, la.rate)

        return atual, melhor


async def load_return_policy(session: AsyncSession) -> ReturnPolicy:
    chaves = [k for chaves in MATRIX_KEYS.values() for k in chaves]
    valores = await settings_repo.get_values(
        session, [*chaves, CRAFT_FAMILIES_KEY, REFINE_RESOURCES_KEY, UNMAPPED_KEY]
    )

    matrices = {
        atividade: ReturnMatrix(*(valores.get(chave) for chave in chaves_atividade))
        for atividade, chaves_atividade in MATRIX_KEYS.items()
    }

    return ReturnPolicy(
        matrices=matrices,
        craft_families=valores.get(CRAFT_FAMILIES_KEY) or {},
        refine_resources=valores.get(REFINE_RESOURCES_KEY),
        unmapped=valores.get(UNMAPPED_KEY) or {},
    )


def return_out(
    resolucao: ReturnResolution,
    melhor: CityBonus,
    nome_da_cidade: dict[str, str] | None = None,
) -> ReturnOut:
    """Traduz a resolução para a resposta, com o nome visual da cidade."""
    nomes = nome_da_cidade or {}
    return ReturnOut(
        rate=resolucao.rate,
        source=resolucao.source,
        has_city_bonus=resolucao.has_city_bonus,
        use_focus=resolucao.use_focus,
        daily_bonus=resolucao.daily_bonus,
        matrix_rate=resolucao.matrix_rate,
        best_city=melhor.city_slug,
        best_city_name=nomes.get(melhor.city_slug or "", melhor.city_slug),
        rate_at_best_city=melhor.rate_there,
        delta=melhor.delta,
        is_best_city=melhor.is_here,
        mapping_known=melhor.city_slug is not None,
    )
