"""Planos de agricultura e criação."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.calculations.farming import PlanKind
from app.calculations.fees import Strategy
from app.schemas.farming import FarmingResponse
from app.services.farming_service import ORDENACOES, find_farming_plans
from app.services.sourcing import SourcingMode

router = APIRouter(prefix="/farming", tags=["farming"])

ESTACOES = ("farm", "herbgarden", "pasture", "kennel")
TIPOS = {str(k): str(k) for k in PlanKind}

SOURCING_MODE = {
    "CIDADE_UNICA": SourcingMode.SINGLE_CITY,
    "MAIS_BARATO": SourcingMode.CHEAPEST,
    "COMPARAR": SourcingMode.COMPARE,
}


@router.get("/plans", response_model=FarmingResponse)
async def farming_plans(
    session: SessionDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon", description="onde comprar semente, filhote e ração"),
    sell_location: str | None = Query(None, description="padrão: mesma cidade da compra"),
    setup_fee_pct: float | None = Query(None, ge=0, le=1),
    sales_tax_pct: float | None = Query(None, ge=0, le=1),
    premium: bool | None = Query(None),
    station: str | None = Query(None, description=f"um de {ESTACOES}"),
    kind: str | None = Query(None, description="CULTIVO | CRIACAO | PRODUTO"),
    tier: int | None = Query(None, ge=1, le=8),
    strategy: str = Query("IMEDIATA", description="IMEDIATA | PACIENTE"),
    # Prata por dia é o padrão porque é o que compara 22 horas de fazenda com
    # 28 dias de criação. Ordenar por lucro por ciclo premiaria o que é lento.
    sort_by: str = Query("profit_per_day", description=f"um de {ORDENACOES}"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    sourcing_mode: str = Query(
        "CIDADE_UNICA", description="CIDADE_UNICA | MAIS_BARATO | COMPARAR"
    ),
    limit: int = Query(40, ge=1, le=200),
) -> FarmingResponse:
    return await find_farming_plans(
        session,
        server=server,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        station=station if station in ESTACOES else None,
        kind=TIPOS.get((kind or "").upper()),
        tier=tier,
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        sort_by=sort_by,
        sort_desc=sort_dir == "desc",
        sourcing_mode=SOURCING_MODE.get(sourcing_mode.upper(), SourcingMode.SINGLE_CITY),
        limit=limit,
    )
