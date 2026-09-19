"""Política da especialização: qual nível vale para qual item.

`calculations/specialization.py` tem a fórmula. Aqui fica o que ela não pode
saber: quantos pontos de eficiência cada tipo de peça dá por nível (dado de
configuração) e a qual nó do Destiny Board um `unique_name` pertence.

## Três granularidades, porque o jogo não tem só uma

**Craft de equipamento é por item.** Quem especializou Capuz de Mercenário não
especializou Capuz de Caçador: são nós diferentes do Destiny Board, e o Focus de
um não tem nada a ver com o do outro. A fase 16 tratou tudo pela regra do
refino, e isso estava errado.

**Refino é por tier.** A fase 16 assumiu que bastava um nível por família, e a
aba `Spec` da planilha de referência **desmente**: ela lista Couro Trabalhado
(T4) com 23, Curtido (T5) com 20 e Endurecido (T6) com 10 — níveis diferentes
para a mesma família, porque no Destiny Board são nós separados.

**A família continua existindo** como atalho, para quem subiu a linha por igual
e não quer preencher cinco tiers.

Por isso a chave de `item_levels` **preserva a granularidade digitada**:
`T5_PLANKS` vale só para o T5; `PLANKS` vale para todos os tiers. O
encantamento sempre sai, porque nunca é nó próprio.

A saída **não** é pedir centenas de campos. É deixar o usuário informar o que
ele de fato produz — costuma ser um punhado — e manter o resto em zero, com
`assumes_zero_spec` dizendo isso, exatamente como já acontece hoje.

## Precedência

    item com tier  →  linha do item  →  família  →  zero

Do mais específico para o mais geral.
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

# `T4_MAIN_SWORD@2` -> `MAIN_SWORD`. O tier e o encantamento saem: o nó do
# Destiny Board é da **linha** do item, não de cada variante.
_SEM_TIER = re.compile(r"^T\d_")
_SUFIXO = re.compile(r"(?:_LEVEL\d+)?(?:@\d)?$")

# Quando a configuração não trouxer a tabela, vale 250 — é o valor "único" que
# todo nó de especialização dá, e o padrão de onde as exceções (BAG, CAPE)
# se afastam. Cair aqui não é chute: é o caso geral.
DEFAULT_REFINING_FCE = 250.0

# As cinco linhas de recurso. Fonte única: a rota importa daqui em vez de
# repetir a lista, e a configuração pode sobrescrever.
#
# Por que existe um padrão em vez de exigir a configuração: sem ele, um banco
# sem a 0009 aplicada aceitaria o spec que o usuário informou e o ignoraria em
# silêncio — o pior dos dois mundos, porque a tela diria "spec 60" e a conta
# usaria zero.
DEFAULT_FAMILIES = ("LEATHER", "CLOTH", "PLANKS", "METALBAR", "STONEBLOCK")

# Prefixo da linha do item -> tipo de peça, para achar os pontos por nível.
#
# Os prefixos foram conferidos contra o catálogo importado, não supostos:
# `2H` (610 itens), `MAIN` (190), `ARMOR`/`HEAD`/`SHOES` (180 cada),
# `CAPEITEM` (140), `OFF` (96), `2H_TOOL` (94), `BAG` (12).
#
# A ordem importa: `2H_TOOL` precisa ser testado antes de `2H`, e `_GATHERER_`
# antes de `ARMOR`/`HEAD`/`SHOES`, senão a roupa de coletor vira armadura.
_TIPOS: tuple[tuple[str, str], ...] = (
    ("2H_TOOL", "GATHERER"),
    ("BAG", "BAG"),
    ("CAPEITEM", "CAPE"),
    ("BACKPACK", "BACKPACK"),
    ("MAIN", "MAIN"),
    ("2H", "2H"),
    ("OFF", "OFF_PRIMARY"),
    ("ARMOR", "ARMOR"),
    ("HEAD", "HEAD"),
    ("SHOES", "SHOES"),
    ("MEAL", "FOOD"),
    ("FISH", "FOOD"),
    ("POTION", "POOT"),
    ("ALCHEMY", "POOT"),
)


def family_of(unique_name: str) -> str | None:
    """Família de recurso: PLANKS, METALBAR, LEATHER, CLOTH, STONEBLOCK…"""
    match = _FAMILIA.match(unique_name)
    return match.group(1) if match else None


def tier_key_of(unique_name: str) -> str:
    """O item com o tier, sem encantamento. `T4_MAIN_SWORD@2` -> `T4_MAIN_SWORD`.

    O encantamento **nunca** é nó próprio de especialização — `T4_PLANKS` e
    `T4_PLANKS_LEVEL2@2` são a mesma decisão de spec. O tier, esse pode ser.
    """
    return _SUFIXO.sub("", unique_name.strip().upper())


def spec_key_of(unique_name: str) -> str:
    """A linha do item, sem tier. `T4_MAIN_SWORD@2` -> `MAIN_SWORD`."""
    return _SEM_TIER.sub("", tier_key_of(unique_name))


def normalize_spec_key(informado: str) -> str:
    """Normaliza o que o usuário digitou, **preservando a granularidade dele**.

    `T5_PLANKS` continua `T5_PLANKS`; `PLANKS` continua `PLANKS`. Só o
    encantamento sai. É o que permite as duas granularidades coexistirem — ver
    `profile_of`.
    """
    return tier_key_of(informado)


def piece_type_of(unique_name: str) -> str | None:
    """Tipo de peça, para escolher os pontos por nível.

    `None` quando nenhum prefixo casa — e aí o cálculo usa o valor geral de 250
    em vez de inventar um tipo. Errar o tipo mudaria o Focus; não reconhecer o
    tipo só usa o caso comum.
    """
    chave = spec_key_of(unique_name)
    for prefixo, tipo in _TIPOS:
        if chave == prefixo or chave.startswith(prefixo + "_"):
            return tipo
    return None


@dataclass(frozen=True)
class SpecializationPolicy:
    """Níveis informados, prontos para virar custo de Focus."""

    levels: dict[str, int] = field(default_factory=dict)
    """Por **família** de recurso. `LEATHER -> 60`. Ausente significa zero."""

    item_levels: dict[str, int] = field(default_factory=dict)
    """Por item. `T5_PLANKS -> 100` (só o T5) ou `MAIN_SWORD -> 80` (a linha).

    A granularidade é a que o usuário digitou, e a com tier vence a de linha.
    Ambas vencem a família.
    """

    mastery_levels: dict[str, int] = field(default_factory=dict)
    mastery2_levels: dict[str, int] = field(default_factory=dict)
    fce_per_spec_level: dict[str, float] = field(default_factory=dict)
    families: tuple[str, ...] = DEFAULT_FAMILIES

    _memoria: dict[str, SpecProfile] = field(default_factory=dict, repr=False, compare=False)
    """Perfil já resolvido, por item. **Por requisição**, como a política.

    `profile_of` é CPU pura e determinística — casa prefixo, consulta três
    dicionários — e era reconstruída 43.900 vezes numa só chamada de
    `/refining`, sempre sobre os mesmos níveis informados. A política nasce e
    morre dentro de uma requisição, e a memória nasce junto: não há como
    servir um perfil de níveis antigos, porque não há política antiga.

    `compare=False` mantém a igualdade entre duas políticas sendo sobre os
    níveis, não sobre o que cada uma resolveu antes.

    **Esta memória rendeu zero, e a medição está aqui para não se perder.** As
    43.900 chamadas vinham de dentro da recursão da cadeia, e o `ChainCache`
    (fase 33) já as eliminou: medido com e sem, intercalado, `/refining(200)`
    deu 1794 ms contra 1765 ms — diferença dentro do ruído. Ela fica como
    seguro barato, porque o trabalho passa a ser O(1) por item em vez de O(n)
    por chamada, e porque nem todo caminho até aqui passa pela cadeia. Não fica
    como ganho medido, que seria mentira.
    """

    @property
    def informed(self) -> bool:
        """Se o usuário informou spec em alguma família ou item."""
        return (
            any(self.levels.values())
            or any(self.item_levels.values())
            or any(self.mastery_levels.values())
        )

    def profile_of(self, unique_name: str) -> SpecProfile:
        memorizado = self._memoria.get(unique_name)
        if memorizado is None:
            memorizado = self._resolver_perfil(unique_name)
            self._memoria[unique_name] = memorizado
        return memorizado

    def _resolver_perfil(self, unique_name: str) -> SpecProfile:
        # 1. Nível do item. Duas granularidades, nesta ordem:
        #
        #    `T5_PLANKS` — só aquele tier. É a granularidade do refino: a aba
        #    `Spec` da planilha de referência lista Couro Trabalhado (T4),
        #    Curtido (T5) e Endurecido (T6) com níveis **diferentes** (23, 20,
        #    10), porque no Destiny Board eles são nós separados.
        #
        #    `PLANKS` / `MAIN_SWORD` — a linha inteira, todos os tiers. É o
        #    atalho para quem subiu a linha por igual, e a granularidade natural
        #    do craft de equipamento.
        #
        # O mais específico vence, que é a mesma regra da precedência geral.
        com_tier = tier_key_of(unique_name)
        linha = spec_key_of(unique_name)
        chave = com_tier if com_tier in self.item_levels else linha
        nivel_item = self.item_levels.get(chave)
        if nivel_item:
            return SpecProfile(
                spec_level=nivel_item,
                mastery_level=self.mastery_levels.get(chave, 0),
                mastery2_level=self.mastery2_levels.get(chave, 0),
                fce_per_spec_level=self._fce(piece_type_of(unique_name)),
            )

        # 2. Nível da família, que é a unidade certa para refino.
        familia = family_of(unique_name)
        if familia is not None and familia in self.families:
            return SpecProfile(
                spec_level=self.levels.get(familia, 0),
                mastery_level=self.mastery_levels.get(familia, 0),
                mastery2_level=self.mastery2_levels.get(familia, 0),
                fce_per_spec_level=self._fce("REFINING"),
            )

        # 3. Nada informado: spec 0. Superestima o Focus, que é o lado seguro.
        return SpecProfile(fce_per_spec_level=self._fce(piece_type_of(unique_name)))

    def focus_cost_of(self, unique_name: str, base_focus: float) -> FocusCost:
        return focus_cost_with_spec(base_focus, self.profile_of(unique_name))

    def _fce(self, tipo: str | None) -> float:
        if tipo is None:
            return DEFAULT_REFINING_FCE
        valor = self.fce_per_spec_level.get(tipo)
        return DEFAULT_REFINING_FCE if valor is None else float(valor)


def parse_item_levels(raw: str | None) -> dict[str, int]:
    """`T5_PLANKS:100,MAIN_SWORD:80` -> `{T5_PLANKS: 100, MAIN_SWORD: 80}`.

    **A granularidade digitada é preservada**: com tier vale só para aquele
    tier, sem tier vale para a linha inteira. O encantamento sempre sai, porque
    nunca é nó próprio.

    Entrada malformada é **ignorada**, não derruba a requisição: um parâmetro
    de URL torto não pode tirar a tela do ar.
    """
    if not raw:
        return {}

    niveis: dict[str, int] = {}
    for parte in raw.split(","):
        item, _, nivel = parte.partition(":")
        item = item.strip()
        if not item:
            continue
        try:
            valor = int(float(nivel))
        except ValueError:
            continue
        niveis[normalize_spec_key(item)] = max(0, min(100, valor))
    return niveis


async def load_specialization_policy(
    session: AsyncSession,
    levels: dict[str, int] | None = None,
    mastery_levels: dict[str, int] | None = None,
    mastery2_levels: dict[str, int] | None = None,
    item_levels: dict[str, int] | None = None,
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
        item_levels={normalize_spec_key(k): v for k, v in (item_levels or {}).items()},
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
        "item_levels": dict(policy.item_levels),
        "families": list(policy.families),
        "halving_points": FOCUS_HALVING_EFFICIENCY,
        "per_mastery_level": FCE_PER_MASTERY_LEVEL,
        "per_spec_level": dict(policy.fce_per_spec_level),
    }
