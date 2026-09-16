"""Escrita e leitura de preços de mercado."""

from dataclasses import asdict
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.market import MarketPrice
from app.models.reference import Location, Server

# Colunas de preço: atualizadas em bloco no UPSERT.
_PRICE_COLUMNS = (
    "sell_price_min",
    "sell_price_min_date",
    "sell_price_max",
    "sell_price_max_date",
    "buy_price_min",
    "buy_price_min_date",
    "buy_price_max",
    "buy_price_max_date",
)


async def upsert_prices(
    session: AsyncSession, records: list[MarketPriceRecord], chunk_size: int = 500
) -> int:
    """UPSERT por (servidor, local, item, qualidade).

    Só grava linhas que tenham ao menos um preço. Uma linha com os quatro campos
    nulos não diz "o mercado está vazio" -- diz "ninguém abriu esse mercado", e
    persistir isso como se fosse observação suja a tabela e o cálculo de frescor.
    """
    payload = [asdict(record) for record in records if record.has_any_price]
    if not payload:
        return 0

    total = 0
    for start in range(0, len(payload), chunk_size):
        chunk = payload[start : start + chunk_size]
        statement = pg_insert(MarketPrice).values(chunk)
        statement = statement.on_conflict_do_update(
            index_elements=[
                MarketPrice.server_id,
                MarketPrice.location_id,
                MarketPrice.item_id,
                MarketPrice.quality,
            ],
            set_={
                **{column: getattr(statement.excluded, column) for column in _PRICE_COLUMNS},
                "observed_at": statement.excluded.observed_at,
                "source_id": statement.excluded.source_id,
            },
        )
        await session.execute(statement)
        total += len(chunk)

    return total


def _price_query(
    server_code: str,
    location_slugs: list[str] | None,
    item_search: str | None,
    tier: int | None,
    enchantment: int | None,
    qualities: list[int] | None,
    tracked_only: bool,
) -> Select:
    statement = (
        select(MarketPrice, Item, Location)
        .join(Item, MarketPrice.item_id == Item.id)
        .join(Location, MarketPrice.location_id == Location.id)
        .join(Server, MarketPrice.server_id == Server.id)
        .where(Server.code == server_code)
    )

    if location_slugs:
        statement = statement.where(Location.slug.in_(location_slugs))
    if item_search:
        pattern = f"%{item_search.strip()}%"
        statement = statement.where(
            Item.unique_name.ilike(pattern)
            | Item.display_name_en.ilike(pattern)
            | Item.display_name_pt.ilike(pattern)
        )
    if tier is not None:
        statement = statement.where(Item.tier == tier)
    if enchantment is not None:
        statement = statement.where(Item.enchantment == enchantment)
    if qualities:
        statement = statement.where(MarketPrice.quality.in_(qualities))
    if tracked_only:
        statement = statement.where(Item.is_tracked.is_(True))

    return statement


_SORTABLE = {
    "sell_price_min": MarketPrice.sell_price_min,
    "sell_price_max": MarketPrice.sell_price_max,
    "buy_price_min": MarketPrice.buy_price_min,
    "buy_price_max": MarketPrice.buy_price_max,
    "observed_at": MarketPrice.observed_at,
    "item": Item.unique_name,
    "tier": Item.tier,
}


async def search_prices(
    session: AsyncSession,
    server_code: str,
    location_slugs: list[str] | None = None,
    item_search: str | None = None,
    tier: int | None = None,
    enchantment: int | None = None,
    qualities: list[int] | None = None,
    tracked_only: bool = False,
    sort_by: str = "item",
    descending: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[tuple[MarketPrice, Item, Location]], int]:
    base = _price_query(
        server_code, location_slugs, item_search, tier, enchantment, qualities, tracked_only
    )

    total = await session.scalar(
        select(func.count()).select_from(base.subquery())
    )

    column = _SORTABLE.get(sort_by, Item.unique_name)
    # NULL em preço significa "sem ordem". Ordenar por preço não pode jogar
    # essas linhas para o topo como se fossem as mais baratas.
    ordering = column.desc().nulls_last() if descending else column.asc().nulls_last()

    rows = await session.execute(
        base.order_by(ordering, Item.unique_name, Location.slug, MarketPrice.quality)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), int(total or 0)


async def freshest_observation(session: AsyncSession, server_code: str) -> datetime | None:
    """Quando a coleta mais recente entrou para este servidor."""
    return await session.scalar(
        select(func.max(MarketPrice.observed_at))
        .join(Server, MarketPrice.server_id == Server.id)
        .where(Server.code == server_code)
    )


async def count_prices(session: AsyncSession, server_code: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(MarketPrice)
            .join(Server, MarketPrice.server_id == Server.id)
            .where(Server.code == server_code)
        )
        or 0
    )


async def sell_quotes_by_city(
    session: AsyncSession,
    server_code: str,
    item_unique_names: list[str],
    location_slugs: list[str],
) -> list[tuple[str, str, str, int | None, datetime | None]]:
    """Ordem de venda mais barata de cada item em cada cidade pedida.

    É o preço que quem *compra* material paga (requisito 7: quem compra do
    mercado paga `sell_price_min`). Devolve uma linha por (item, cidade), a da
    menor qualidade encontrada -- misturar qualidades no custo compararia coisas
    diferentes.

    `sell_price_min` volta como `None` quando não há ordem naquela cidade. Isso
    é ausência de dado, não preço zero: quem chama decide o que fazer com ela.
    """
    if not item_unique_names or not location_slugs:
        return []

    statement = (
        select(
            Item.unique_name,
            Location.slug,
            Location.display_name,
            MarketPrice.sell_price_min,
            MarketPrice.sell_price_min_date,
            MarketPrice.quality,
        )
        .join(Item, MarketPrice.item_id == Item.id)
        .join(Location, MarketPrice.location_id == Location.id)
        .join(Server, MarketPrice.server_id == Server.id)
        .where(
            Server.code == server_code,
            Item.unique_name.in_(item_unique_names),
            Location.slug.in_(location_slugs),
        )
        .order_by(Item.unique_name, Location.slug, MarketPrice.quality)
    )

    vistos: set[tuple[str, str]] = set()
    linhas: list[tuple[str, str, str, int | None, datetime | None]] = []
    for nome, slug, display, preco, data, _quality in (await session.execute(statement)).all():
        chave = (nome, slug)
        if chave in vistos:
            continue
        vistos.add(chave)
        linhas.append((nome, slug, display, preco, data))
    return linhas
