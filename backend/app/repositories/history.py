"""Histórico de preço e cotação de gold."""

from dataclasses import asdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.aodp.normalization import GoldPriceRecord, MarketHistoryRecord
from app.models.catalog import Item
from app.models.market import GoldPrice, MarketHistory
from app.models.reference import Location, Server


async def upsert_history(
    session: AsyncSession, records: list[MarketHistoryRecord], chunk_size: int = 1000
) -> int:
    """UPSERT por bucket.

    Recoletar uma janela sobrescreve os buckets: o AODP pode revisar a agregação
    conforme novos dados de jogadores chegam. `is_outlier` não entra aqui -- ele
    é calculado depois, com a janela inteira à vista.
    """
    if not records:
        return 0

    payload = [asdict(record) for record in records]
    total = 0
    for start in range(0, len(payload), chunk_size):
        chunk = payload[start : start + chunk_size]
        statement = pg_insert(MarketHistory).values(chunk)
        statement = statement.on_conflict_do_update(
            index_elements=[
                MarketHistory.server_id,
                MarketHistory.location_id,
                MarketHistory.item_id,
                MarketHistory.quality,
                MarketHistory.timescale,
                MarketHistory.bucket_ts,
            ],
            set_={
                "item_count": statement.excluded.item_count,
                "avg_price": statement.excluded.avg_price,
                "source_id": statement.excluded.source_id,
                "ingested_at": statement.excluded.ingested_at,
            },
        )
        await session.execute(statement)
        total += len(chunk)
    return total


async def load_series(
    session: AsyncSession,
    server_code: str,
    item_unique_name: str,
    location_slugs: list[str] | None = None,
    quality: int | None = None,
    timescale: int = 24,
    since: datetime | None = None,
) -> list[tuple[MarketHistory, Location]]:
    statement = (
        select(MarketHistory, Location)
        .join(Item, MarketHistory.item_id == Item.id)
        .join(Location, MarketHistory.location_id == Location.id)
        .join(Server, MarketHistory.server_id == Server.id)
        .where(
            Server.code == server_code,
            Item.unique_name == item_unique_name,
            MarketHistory.timescale == timescale,
        )
        .order_by(Location.slug, MarketHistory.bucket_ts)
    )
    if location_slugs:
        statement = statement.where(Location.slug.in_(location_slugs))
    if quality is not None:
        statement = statement.where(MarketHistory.quality == quality)
    if since is not None:
        statement = statement.where(MarketHistory.bucket_ts >= since)

    return list((await session.execute(statement)).all())


async def mark_outliers(session: AsyncSession, marks: dict[tuple, bool]) -> int:
    """Aplica a marcação calculada fora do banco.

    A chave é (server_id, location_id, item_id, quality, timescale, bucket_ts).
    Só grava o que mudou: reescrever a janela inteira a cada coleta geraria
    escrita inútil numa tabela que cresce sem parar.
    """
    changed = 0
    for key, is_outlier in marks.items():
        row = await session.get(MarketHistory, key)
        if row is not None and row.is_outlier != is_outlier:
            row.is_outlier = is_outlier
            changed += 1
    await session.flush()
    return changed


async def upsert_gold(session: AsyncSession, records: list[GoldPriceRecord]) -> int:
    if not records:
        return 0
    statement = pg_insert(GoldPrice).values([asdict(record) for record in records])
    statement = statement.on_conflict_do_update(
        index_elements=[GoldPrice.server_id, GoldPrice.ts],
        set_={"price": statement.excluded.price, "source_id": statement.excluded.source_id},
    )
    await session.execute(statement)
    return len(records)


async def load_gold(
    session: AsyncSession, server_code: str, since: datetime | None = None, limit: int = 500
) -> list[GoldPrice]:
    statement = (
        select(GoldPrice)
        .join(Server, GoldPrice.server_id == Server.id)
        .where(Server.code == server_code)
        .order_by(GoldPrice.ts.desc())
        .limit(limit)
    )
    if since is not None:
        statement = statement.where(GoldPrice.ts >= since)
    rows = list((await session.scalars(statement)).all())
    return list(reversed(rows))


async def count_history(session: AsyncSession, server_code: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(MarketHistory)
            .join(Server, MarketHistory.server_id == Server.id)
            .where(Server.code == server_code)
        )
        or 0
    )
