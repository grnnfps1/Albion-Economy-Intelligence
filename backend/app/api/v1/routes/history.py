"""Histórico de preço e cotação de gold."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep
from app.repositories import history as history_repo
from app.repositories import items as items_repo
from app.schemas.history import GoldResponse, HistoryResponse
from app.services.history_service import DATA_SOURCE_NOTE, build_gold, build_series

router = APIRouter(tags=["history"])

# Períodos do requisito 14. time-scale 1 (hora) só faz sentido em janela curta.
PERIODOS = {"24H": 1, "3D": 3, "7D": 7, "14D": 14, "30D": 30, "90D": 90}


@router.get("/market/history", response_model=HistoryResponse)
async def history(
    session: SessionDep,
    item: str = Query(description="Id técnico, ex.: T5_LEATHER"),
    server: str = Query("west"),
    period: str = Query("7D", description=f"um de {list(PERIODOS)}"),
    locations: str | None = Query(None, description="slugs separados por vírgula"),
    quality: int | None = Query(None, ge=1, le=5),
    timescale: int | None = Query(None, description="1, 6 ou 24 horas por bucket"),
) -> HistoryResponse:
    if period not in PERIODOS:
        raise HTTPException(400, f"período inválido: {period}. Use {list(PERIODOS)}")

    days = PERIODOS[period]
    # Janela curta pede bucket fino; janela longa com bucket de 1h viraria
    # milhares de pontos que o gráfico não consegue mostrar.
    escala = timescale or (1 if days <= 3 else 24)

    catalogo = await items_repo.get_by_unique_name(session, item)
    if catalogo is None:
        raise HTTPException(404, f"item fora do catálogo: {item}")

    rows = await history_repo.load_series(
        session,
        server_code=server,
        item_unique_name=item,
        location_slugs=[s.strip() for s in locations.split(",")] if locations else None,
        quality=quality,
        timescale=escala,
        since=datetime.now(UTC) - timedelta(days=days),
    )
    series = build_series(rows)

    return HistoryResponse(
        server=server,
        item=item,
        item_name=catalogo.display_name_pt or catalogo.display_name_en,
        timescale=escala,
        period_days=days,
        total_points=sum(len(one.points) for one in series),
        series=series,
        data_source_note=DATA_SOURCE_NOTE,
    )


@router.get("/gold", response_model=GoldResponse)
async def gold(
    session: SessionDep,
    server: str = Query("west"),
    days: int = Query(7, ge=1, le=365),
) -> GoldResponse:
    rows = await history_repo.load_gold(
        session, server, since=datetime.now(UTC) - timedelta(days=days)
    )
    return build_gold(server, rows)
