"""Ranking de Focus."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.schemas.focus import FocusResponse
from app.services.focus_service import build_focus_ranking

router = APIRouter(prefix="/focus", tags=["focus"])

ORDENACOES = ("realizable_profit", "profit_per_focus")


@router.get("/ranking", response_model=FocusResponse)
async def focus_ranking(
    session: SessionDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon"),
    sell_location: str | None = Query(None),
    # Sem orçamento, o único teto é o mercado. Com orçamento, o ranking passa a
    # responder "onde gasto o Focus que eu tenho" em vez de "qual a melhor taxa".
    focus_budget: float | None = Query(None, ge=0, description="Focus disponível."),
    horizon_days: int = Query(7, ge=1, le=90, description="Em quantos dias pretende escoar."),
    return_rate: float | None = Query(None, ge=0, le=1),
    station_fee: float | None = Query(None, ge=0),
    setup_fee_pct: float | None = Query(None, ge=0, le=1),
    sales_tax_pct: float | None = Query(None, ge=0, le=1),
    premium: bool | None = Query(None),
    sourcing: str = Query("MAIS_BARATO"),
    strategy: str = Query("IMEDIATA"),
    sort_by: str = Query("realizable_profit", description=f"um de {ORDENACOES}"),
    limit: int = Query(30, ge=1, le=100),
) -> FocusResponse:
    modos = {"MERCADO": Sourcing.MARKET, "PRODUZIR": Sourcing.CRAFT,
             "MAIS_BARATO": Sourcing.CHEAPEST}
    return await build_focus_ranking(
        session,
        server=server,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        focus_budget=focus_budget,
        horizon_days=horizon_days,
        return_rate=return_rate,
        station_fee=station_fee,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        sourcing=modos.get(sourcing.upper(), Sourcing.CHEAPEST),
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        sort_by=sort_by if sort_by in ORDENACOES else "realizable_profit",
        limit=limit,
    )
