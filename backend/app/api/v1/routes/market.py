"""Preços de mercado."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.repositories import market as market_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.schemas.market import MarketPricePage
from app.services.market_service import DATA_SOURCE_NOTE, to_price_out

router = APIRouter(prefix="/market", tags=["market"])

SORTABLE = ("item", "tier", "sell_price_min", "sell_price_max", "buy_price_min",
            "buy_price_max", "observed_at")


@router.get("/prices", response_model=MarketPricePage)
async def prices(
    session: SessionDep,
    settings: SettingsDep,
    server: str = Query("west", description="west | east | europe"),
    locations: str | None = Query(None, description="slugs separados por vírgula"),
    search: str | None = Query(None, description="id técnico ou nome visual"),
    tier: int | None = Query(None, ge=1, le=8),
    enchantment: int | None = Query(None, ge=0, le=4),
    qualities: str | None = Query(None, description="ex.: 1,2"),
    tracked_only: bool = Query(False),
    sort_by: str = Query("item", description=f"um de {SORTABLE}"),
    descending: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> MarketPricePage:
    rows, total = await market_repo.search_prices(
        session,
        server_code=server,
        location_slugs=[s.strip() for s in locations.split(",")] if locations else None,
        item_search=search,
        tier=tier,
        enchantment=enchantment,
        qualities=[int(q) for q in qualities.split(",")] if qualities else None,
        tracked_only=tracked_only,
        sort_by=sort_by if sort_by in SORTABLE else "item",
        descending=descending,
        limit=limit,
        offset=offset,
    )

    # Uma consulta de liquidez para a página inteira, não uma por linha.
    sinais = await liquidity_by_item_location(
        session, server, [item.id for _price, item, _location in rows]
    )

    now = datetime.now(UTC)
    return MarketPricePage(
        server=server,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        descending=descending,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        prices=[
            to_price_out(
                price, item, location, now, settings,
                sinais.get((item.id, location.id, price.quality)),
            )
            for price, item, location in rows
        ],
    )
