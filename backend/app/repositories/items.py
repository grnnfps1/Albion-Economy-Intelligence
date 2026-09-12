"""Consulta ao catálogo de itens."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Item
from app.models.reference import ItemCategory


def _apply_filters(
    statement: Select,
    search: str | None,
    tier: int | None,
    enchantment: int | None,
    category_code: str | None,
    tracked_only: bool,
) -> Select:
    statement = statement.where(Item.active.is_(True))

    if search:
        # Busca tanto pelo id técnico quanto pelo nome visual: o jogador digita
        # "couro", o desenvolvedor digita "T5_LEATHER".
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Item.unique_name.ilike(pattern),
                Item.display_name_en.ilike(pattern),
                Item.display_name_pt.ilike(pattern),
            )
        )
    if tier is not None:
        statement = statement.where(Item.tier == tier)
    if enchantment is not None:
        statement = statement.where(Item.enchantment == enchantment)
    if category_code:
        statement = statement.join(ItemCategory, Item.category_id == ItemCategory.id).where(
            ItemCategory.code == category_code
        )
    if tracked_only:
        statement = statement.where(Item.is_tracked.is_(True))
    return statement


async def search_items(
    session: AsyncSession,
    search: str | None = None,
    tier: int | None = None,
    enchantment: int | None = None,
    category_code: str | None = None,
    tracked_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Item], int]:
    """Devolve a página e o total, para o frontend paginar sem adivinhar."""
    base = _apply_filters(
        select(Item), search, tier, enchantment, category_code, tracked_only
    )

    total = await session.scalar(
        _apply_filters(
            select(func.count(Item.id)), search, tier, enchantment, category_code, tracked_only
        )
    )

    rows = await session.scalars(
        base.order_by(Item.tier.nulls_last(), Item.base_name, Item.enchantment)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), int(total or 0)


async def count_items(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count(Item.id))) or 0
    tracked = (
        await session.scalar(select(func.count(Item.id)).where(Item.is_tracked.is_(True))) or 0
    )
    return {"total": int(total), "tracked": int(tracked)}


async def get_by_unique_name(session: AsyncSession, unique_name: str) -> Item | None:
    return await session.scalar(select(Item).where(Item.unique_name == unique_name))
