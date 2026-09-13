"""Consulta às receitas."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial


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
        .options(selectinload(Recipe.materials).selectinload(RecipeMaterial.recipe))
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


async def load_items(session: AsyncSession, item_ids: list[int]) -> dict[int, Item]:
    if not item_ids:
        return {}
    rows = await session.scalars(select(Item).where(Item.id.in_(item_ids)))
    return {item.id: item for item in rows.all()}


async def count_recipes(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Recipe)) or 0)
