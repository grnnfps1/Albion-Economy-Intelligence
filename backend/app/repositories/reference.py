"""Leitura das tabelas de referência."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference import DataSource, ItemCategory, Location, Server


async def list_servers(session: AsyncSession, only_active: bool = True) -> list[Server]:
    statement = select(Server).order_by(Server.id)
    if only_active:
        statement = statement.where(Server.active.is_(True))
    return list((await session.scalars(statement)).all())


async def list_locations(session: AsyncSession, only_active: bool = True) -> list[Location]:
    # Cidades primeiro, Black Market depois: ele não é uma cidade e não deve
    # aparecer misturado na lista (requisito 31).
    statement = select(Location).order_by(Location.kind, Location.display_name)
    if only_active:
        statement = statement.where(Location.active.is_(True))
    return list((await session.scalars(statement)).all())


async def list_categories(session: AsyncSession) -> list[ItemCategory]:
    return list((await session.scalars(select(ItemCategory).order_by(ItemCategory.code))).all())


async def get_data_source(session: AsyncSession, code: str) -> DataSource | None:
    return await session.scalar(select(DataSource).where(DataSource.code == code))
