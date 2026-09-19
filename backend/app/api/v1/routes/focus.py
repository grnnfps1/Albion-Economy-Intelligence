"""Ranking de Focus."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.api.v1.routes._spec_params import (
    SPEC_ITEMS_DESC,
    item_levels_from,
    spec_levels_from,
)
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
    station_fee_per_100_nutrition: float | None = Query(None, ge=0),
    # Especialização por família de recurso (0-100). Sem informar, a conta
    # assume spec 0 e a resposta avisa.
    spec_leather: int = Query(0, ge=0, le=100, description="Spec de couro."),
    spec_cloth: int = Query(0, ge=0, le=100, description="Spec de tecido."),
    spec_planks: int = Query(0, ge=0, le=100, description="Spec de tábuas."),
    spec_metalbar: int = Query(0, ge=0, le=100, description="Spec de barras."),
    spec_stoneblock: int = Query(0, ge=0, le=100, description="Spec de blocos."),
    spec_items: str | None = Query(None, description=SPEC_ITEMS_DESC),
    focus_per_day: float | None = Query(
        None, ge=0,
        description=(
            "Focus que regenera por dia — 10.000 numa conta Premium. É o que "
            "limita a produção diária de craft e refino; craft não é limitado "
            "por tempo."
        ),
    ),
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
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        spec_levels=spec_levels_from(
            spec_leather, spec_cloth, spec_planks, spec_metalbar, spec_stoneblock
        ),
        spec_item_levels=item_levels_from(spec_items),
        focus_per_day=focus_per_day,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        sourcing=modos.get(sourcing.upper(), Sourcing.CHEAPEST),
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        sort_by=sort_by if sort_by in ORDENACOES else "realizable_profit",
        limit=limit,
    )
