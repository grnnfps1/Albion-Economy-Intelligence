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

from app.calculations.returns import (
    Activity,
    ReturnComponents,
    ReturnResolution,
    bonus_parts,
    resolve_return_rate,
)
from app.repositories import settings_repo
from app.repositories.reference import list_locations
from app.schemas.crafting import BonusPartOut, ReturnOut

CRAFT_FAMILIES_KEY = "crafting.city_bonus_families"
REFINE_RESOURCES_KEY = "refining.city_bonus_resources"
UNMAPPED_KEY = "crafting.city_bonus_unmapped"

# Os quatro componentes de `B`. A matriz de valores fixos da fase 14 saiu na
# fase 20: o que se guarda agora é o bônus oficial, e a taxa é derivada.
COMPONENT_KEYS = (
    "crafting.return_bonus.city_base",
    "refining.return_bonus.city",
    "crafting.return_bonus.city",
    "crafting.return_bonus.focus",
)

# Locais sem a base de cidade. Quem refina em ilha tem 0% sem Focus e 37,1%
# com — é o que a base zerada produz.
ISLAND_KINDS = frozenset({"island"})

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
    components: ReturnComponents = field(default_factory=ReturnComponents)
    island_slugs: frozenset[str] = frozenset()
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

        `daily_bonus` entra **em `B`**, junto dos outros componentes — não
        somado ao `RRR` já convertido. Foi essa a confusão que fazia as tabelas
        publicadas não fecharem.
        """
        cidade_bonus = self.bonus_city(activity, unique_name)
        tem_bonus = cidade_bonus is not None and cidade_bonus == city_slug
        na_ilha = city_slug in self.island_slugs

        atual = resolve_return_rate(
            self.components, activity, tem_bonus, use_focus, na_ilha,
            daily_bonus, override,
        )

        # Quanto renderia na cidade do bônus, com os mesmos parâmetros. A ilha
        # nunca é a cidade do bônus, então a comparação sai de uma cidade real.
        if cidade_bonus is None:
            melhor = CityBonus(None, atual.rate, None)
        else:
            la = resolve_return_rate(
                self.components, activity, True, use_focus, False,
                daily_bonus, override,
            )
            melhor = CityBonus(cidade_bonus, atual.rate, la.rate)

        return atual, melhor

    def options(
        self,
        activity: Activity,
        unique_name: str,
        locations: list[tuple[str, str, bool]],
        use_focus: bool,
        daily_bonus: float = 0.0,
        override: float | None = None,
    ) -> list["ReturnOption"]:
        """O retorno que cada local daria, para **esta** família.

        A informação já existia no motor desde a fase 20; o que faltava era ela
        aparecer **antes** do cálculo. Um usuário em Caerleon sem Focus via 27
        linhas vermelhas e nenhuma pista de que trocar de cidade resolveria — o
        motor sabia, e só contava depois.

        `locations` vem como `(slug, nome, é ilha)` porque quem sabe quais
        locais existem é o repositório, não esta política.
        """
        opcoes: list[ReturnOption] = []
        for slug, nome, e_ilha in locations:
            resolucao, _ = self.resolve(
                activity, unique_name, slug, use_focus, daily_bonus, override
            )
            opcoes.append(
                ReturnOption(
                    slug=slug,
                    name=nome,
                    rate=resolucao.rate,
                    has_city_bonus=resolucao.has_city_bonus,
                    is_island=e_ilha,
                )
            )
        return opcoes


@dataclass(frozen=True)
class ReturnOption:
    """Um local e o que ele renderia, com os mesmos Focus e bônus do dia."""

    slug: str
    name: str
    rate: float | None
    has_city_bonus: bool
    is_island: bool


async def load_return_policy(session: AsyncSession) -> ReturnPolicy:
    valores = await settings_repo.get_values(
        session,
        [*COMPONENT_KEYS, CRAFT_FAMILIES_KEY, REFINE_RESOURCES_KEY, UNMAPPED_KEY],
    )
    componentes = ReturnComponents(*(valores.get(chave) for chave in COMPONENT_KEYS))

    # Quais locais são ilha. Vem do cadastro e não de uma lista aqui: o dia em
    # que existir um segundo tipo sem base de cidade, ele entra pelo `kind`.
    ilhas = frozenset(
        local.slug
        for local in await list_locations(session, only_active=False)
        if local.kind in ISLAND_KINDS
    )

    return ReturnPolicy(
        components=componentes,
        island_slugs=ilhas,
        craft_families=valores.get(CRAFT_FAMILIES_KEY) or {},
        refine_resources=valores.get(REFINE_RESOURCES_KEY),
        unmapped=valores.get(UNMAPPED_KEY) or {},
    )


def return_out(
    resolucao: ReturnResolution,
    melhor: CityBonus,
    nome_da_cidade: dict[str, str] | None = None,
    components: ReturnComponents | None = None,
    activity: Activity = Activity.REFINING,
    city_label: str | None = None,
) -> ReturnOut:
    """Traduz a resolução para a resposta, com o nome visual da cidade.

    As parcelas de `B` vão junto: `bonus_total` responde *quanto*, e as
    parcelas respondem *de onde* — que é o que permite ao usuário ver se o que
    falta é o Focus ou a cidade.
    """
    nomes = nome_da_cidade or {}
    partes = (
        []
        if components is None
        else bonus_parts(
            components,
            activity,
            resolucao.has_city_bonus,
            resolucao.use_focus,
            resolucao.is_island,
            resolucao.daily_bonus,
            city_label,
        )
    )
    return ReturnOut(
        rate=resolucao.rate,
        source=resolucao.source,
        has_city_bonus=resolucao.has_city_bonus,
        use_focus=resolucao.use_focus,
        daily_bonus=resolucao.daily_bonus,
        assumes_no_daily_bonus=resolucao.assumes_no_daily_bonus,
        matrix_rate=resolucao.formula_rate,
        bonus_total=resolucao.bonus_total,
        is_island=resolucao.is_island,
        components=[
            BonusPartOut(key=p.key, label=p.label, value=p.value, applies=p.applies)
            for p in partes
        ],
        best_city=melhor.city_slug,
        best_city_name=nomes.get(melhor.city_slug or "", melhor.city_slug),
        rate_at_best_city=melhor.rate_there,
        delta=melhor.delta,
        is_best_city=melhor.is_here,
        mapping_known=melhor.city_slug is not None,
    )
