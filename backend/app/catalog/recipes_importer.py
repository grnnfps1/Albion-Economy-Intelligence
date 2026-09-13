"""Importação das receitas a partir do dump oficial.

Mesmo arquivo que o importador de catálogo já baixa. O que muda é o que se lê:
`craftingrequirements`, que traz focus, prata e a lista de materiais.

O formato do dump é irregular e precisa ser tratado, não assumido:

- `craftingrequirements` pode ser **um objeto ou uma lista** de receitas
  alternativas. `T4_PLANKS` tem duas: 2× madeira, ou 1× madeira + token de facção.
- `craftresource` pode ser **um objeto ou uma lista**, e às vezes está ausente.
- Variantes encantadas ficam aninhadas em `enchantments.enchantment[]`, cada uma
  com a própria `craftingrequirements`.
- O material encantado vem com o nome **sem** o sufixo de mercado: o dump diz
  `T4_ROCK_LEVEL1` com `@enchantmentlevel: 1`, enquanto o catálogo e o AODP usam
  `T4_ROCK_LEVEL1@1`. Sem recompor isso, 12 mil materiais ficam órfãos e o custo
  de qualquer craft encantado sai errado para menos.

Material que não é recurso — token de facção, artefato — **não** é elegível ao
retorno de material. Tratar todos igual infla o lucro calculado.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial

log = get_logger(__name__)

# Subcategorias cujo material é elegível ao retorno de material no craft.
#
# ATENÇÃO: esta classificação é a melhor leitura disponível, não uma regra
# verificada no jogo. `cityresources` ficou **de fora** de propósito: é onde o
# dump coloca os tokens de facção, e token consumido num craft quase certamente
# não volta. Se estiver errado, o efeito é subestimar o retorno — erro para o
# lado conservador, que é o lado certo de errar aqui.
#
# Entra na mesma lista de verificação das taxas (docs/04-taxas.md).
RETURNABLE_SUBCATEGORIES = frozenset({"resources", "refinedresources"})


@dataclass
class RecipeImportReport:
    items_with_recipes: int = 0
    recipes_upserted: int = 0
    materials_upserted: int = 0
    materials_missing_from_catalog: int = 0
    recipes_without_materials: int = 0
    missing_examples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "missing_examples"}


def _as_list(value: Any) -> list[dict]:
    """Normaliza os três formatos que o dump usa: objeto, lista ou ausente."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def material_candidates(unique_name: str, enchantment: int) -> tuple[str, ...]:
    """Nomes a tentar no catálogo, em ordem de preferência.

    O dump separa nome e nível de encantamento; o mercado junta os dois. Tenta
    a forma de mercado primeiro e cai no nome literal — alguns materiais têm
    `_LEVELN` no nome de verdade e não são encantamentos (ver docs/01).
    """
    if enchantment > 0 and "@" not in unique_name:
        return (f"{unique_name}@{enchantment}", unique_name)
    return (unique_name,)


@dataclass(frozen=True)
class ParsedRecipe:
    output_unique_name: str
    variant_index: int
    output_quantity: int
    focus_cost: int
    silver_cost: int
    craft_time: float | None
    station_category: str | None
    materials: list[tuple[tuple[str, ...], int]]
    """Cada material é (candidatos_de_nome, quantidade)."""


def parse_entry(entry: dict) -> list[ParsedRecipe]:
    """Extrai todas as receitas de uma entrada do dump, incluindo encantadas."""
    unique_name = entry.get("@uniquename")
    if not unique_name:
        return []

    station = entry.get("@craftingcategory")
    receitas: list[ParsedRecipe] = []

    def acrescentar(destino: str, bloco: dict, indice: int) -> None:
        materiais = [
            (
                material_candidates(
                    recurso["@uniquename"], _as_int(recurso.get("@enchantmentlevel"))
                ),
                _as_int(recurso.get("@count"), 1),
            )
            for recurso in _as_list(bloco.get("craftresource"))
            if recurso.get("@uniquename")
        ]
        receitas.append(
            ParsedRecipe(
                output_unique_name=destino,
                variant_index=indice,
                output_quantity=max(1, _as_int(bloco.get("@amountcrafted"), 1)),
                focus_cost=_as_int(bloco.get("@craftingfocus")),
                silver_cost=_as_int(bloco.get("@silver")),
                craft_time=float(bloco["@time"]) if bloco.get("@time") else None,
                station_category=station,
                materials=materiais,
            )
        )

    for indice, bloco in enumerate(_as_list(entry.get("craftingrequirements"))):
        acrescentar(unique_name, bloco, indice)

    # Variantes encantadas: o identificador de mercado é `{base}@{nivel}`.
    for encantada in _as_list((entry.get("enchantments") or {}).get("enchantment")):
        nivel = _as_int(encantada.get("@enchantmentlevel"))
        if not 1 <= nivel <= 4:
            continue
        for indice, bloco in enumerate(_as_list(encantada.get("craftingrequirements"))):
            acrescentar(f"{unique_name}@{nivel}", bloco, indice)

    return receitas


def parse_dump(metadata: dict) -> list[ParsedRecipe]:
    root = metadata.get("items", metadata)
    receitas: list[ParsedRecipe] = []
    for grupo in root.values():
        entradas: Iterable[Any]
        if isinstance(grupo, list):
            entradas = grupo
        elif isinstance(grupo, dict):
            entradas = [grupo]
        else:
            continue
        for entrada in entradas:
            if isinstance(entrada, dict):
                receitas.extend(parse_entry(entrada))
    return receitas


async def import_recipes(session: AsyncSession, metadata: dict) -> RecipeImportReport:
    report = RecipeImportReport()
    receitas = parse_dump(metadata)

    # Um mapa em memória: 12 mil itens cabem, e evita uma consulta por material.
    rows = await session.execute(select(Item.unique_name, Item.id, Item.subcategory_code))
    catalogo = {nome: (item_id, sub) for nome, item_id, sub in rows.all()}

    alvos = {r.output_unique_name for r in receitas if r.output_unique_name in catalogo}
    report.items_with_recipes = len(alvos)

    # Reimportar substitui: uma receita removida por patch precisa sumir, e
    # comparar campo a campo para decidir isso seria mais frágil do que recriar.
    if alvos:
        ids = [catalogo[nome][0] for nome in alvos]
        await session.execute(delete(Recipe).where(Recipe.output_item_id.in_(ids)))
        await session.flush()

    for receita in receitas:
        destino = catalogo.get(receita.output_unique_name)
        if destino is None:
            continue
        if not receita.materials:
            report.recipes_without_materials += 1
            continue

        linha = Recipe(
            output_item_id=destino[0],
            variant_index=receita.variant_index,
            output_quantity=receita.output_quantity,
            focus_cost=receita.focus_cost,
            silver_cost=receita.silver_cost,
            craft_time=receita.craft_time,
            station_category=receita.station_category,
        )
        session.add(linha)
        await session.flush()
        report.recipes_upserted += 1

        vistos: set[int] = set()
        for candidatos, quantidade in receita.materials:
            material = next(
                (catalogo[nome] for nome in candidatos if nome in catalogo), None
            )
            if material is None:
                report.materials_missing_from_catalog += 1
                if len(report.missing_examples) < 10:
                    report.missing_examples.append(candidatos[0])
                continue
            if material[0] in vistos:
                continue
            vistos.add(material[0])
            session.add(
                RecipeMaterial(
                    recipe_id=linha.id,
                    item_id=material[0],
                    quantity=quantidade,
                    is_returnable=material[1] in RETURNABLE_SUBCATEGORIES,
                )
            )
            report.materials_upserted += 1

    await session.commit()
    log.info("receitas importadas", **report.as_dict())
    return report
