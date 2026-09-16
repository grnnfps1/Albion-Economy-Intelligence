"""Consulta a agricultura e criação."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Item
from app.models.farming import Farmable


async def list_farmables(
    session: AsyncSession,
    station: str | None = None,
    role: str | None = None,
    tier: int | None = None,
    limit: int = 500,
) -> list[Farmable]:
    statement = (
        select(Farmable)
        .join(Item, Farmable.item_id == Item.id)
        .where(Farmable.active.is_(True), Item.active.is_(True))
        .order_by(Item.tier.nulls_last(), Item.unique_name)
        .limit(limit)
    )
    if station:
        statement = statement.where(Farmable.station == station)
    if role:
        statement = statement.where(Farmable.role == role)
    if tier is not None:
        statement = statement.where(Item.tier == tier)
    return list((await session.scalars(statement)).unique().all())


async def food_items(session: AsyncSession, categories: list[str]) -> list[Item]:
    """Itens que servem de ração nas categorias pedidas.

    `nutrition` é o que permite converter "tantos pontos de nutrição" em
    "tantas unidades de cenoura". Sem ele o item não serve de ração, por mais
    que a categoria bata.
    """
    if not categories:
        return []
    statement = (
        select(Item)
        .where(
            Item.food_category.in_(categories),
            Item.nutrition.is_not(None),
            Item.nutrition > 0,
            Item.active.is_(True),
        )
        .order_by(Item.unique_name)
    )
    return list((await session.scalars(statement)).all())
