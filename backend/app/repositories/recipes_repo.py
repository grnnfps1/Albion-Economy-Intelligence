"""Consulta às receitas."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Item
from app.models.recipes import Recipe


async def list_recipes(
    session: AsyncSession,
    output_unique_name: str | None = None,
    station_category: str | None = None,
    tier: int | None = None,
    tracked_only: bool = True,
    limit: int = 100,
) -> list[Recipe]:
    statement = (
        select(Recipe)
        .join(Item, Recipe.output_item_id == Item.id)
        # `Recipe.materials` já é `lazy="selectin"` no modelo, então não há
        # `options` aqui. O que havia era
        # `selectinload(Recipe.materials).selectinload(RecipeMaterial.recipe)`:
        # depois de carregar os materiais, voltava a carregar **a receita de
        # cada material** — que é a receita que já estava na mão. Ninguém no
        # código usa esse back-reference. Custava 20% do tempo da consulta
        # (1864 → 1483 ms nas 12.917 receitas) para reconstruir objetos que
        # já existiam.
        .where(Recipe.active.is_(True), Item.active.is_(True))
        .order_by(Item.tier.nulls_last(), Item.unique_name, Recipe.variant_index)
        .limit(limit)
    )
    if output_unique_name:
        statement = statement.where(Item.unique_name == output_unique_name)
    if station_category:
        statement = statement.where(Recipe.station_category == station_category)
    if tier is not None:
        statement = statement.where(Item.tier == tier)
    if tracked_only:
        statement = statement.where(Item.is_tracked.is_(True))
    return list((await session.scalars(statement)).unique().all())


async def recipes_for_chain(
    session: AsyncSession, seed_item_ids: Sequence[int]
) -> list[Recipe]:
    """As receitas alcançáveis a partir destes itens, e **só** elas.

    ## O problema que resolve

    `/refining` e o calculador pediam `list_recipes(tracked_only=False)` — as
    **12.917 receitas do jogo** — para usar as poucas centenas que a cadeia de
    refino alcança. O filtro estava no lugar errado: o chamador descartava 97%
    do que pedia, depois de o ORM ter construído 41 mil objetos.

    Medido: 1781 ms para 12.917 receitas contra **36 ms** para as 411 do fecho.

    ## Por que o fecho, e não "só as refinadas"

    A tentação é filtrar por `subcategory_code = 'refinedresources'`. **Não
    funciona, e falharia em silêncio:** 120 materiais dessas receitas têm
    receita própria sem serem refinados — recurso bruto encantado, como
    `T4_WOOD_LEVEL1@1`, que se faz de `T4_WOOD` mais material de encantamento.
    Cortar ali faria a cadeia parar de descer e tratar o bruto encantado como
    fim de linha, usando o preço de mercado dele. O custo sairia diferente sem
    nenhum erro aparecer.

    O fecho é exato: parte dos itens pedidos e segue os materiais até não achar
    receita nova. Na prática são **3 rodadas** — a profundidade real do grafo de
    refino, não um número escolhido.

    ## Não precisou de índice novo

    `ix_recipes_output` existe desde a migration inicial, e é exatamente o que
    esta consulta usa.
    """
    alcancados: set[int] = set()
    fronteira = {i for i in seed_item_ids}
    receitas: list[Recipe] = []

    while fronteira:
        lote = await session.scalars(
            select(Recipe).where(
                Recipe.active.is_(True), Recipe.output_item_id.in_(sorted(fronteira))
            )
        )
        encontradas = list(lote.unique().all())
        receitas.extend(encontradas)
        alcancados |= fronteira

        seguinte: set[int] = set()
        for receita in encontradas:
            seguinte.update(material.item_id for material in receita.materials)
        fronteira = seguinte - alcancados

    return receitas


async def load_items(session: AsyncSession, item_ids: list[int]) -> dict[int, Item]:
    if not item_ids:
        return {}
    rows = await session.scalars(select(Item).where(Item.id.in_(item_ids)))
    return {item.id: item for item in rows.all()}


async def count_recipes(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Recipe)) or 0)
