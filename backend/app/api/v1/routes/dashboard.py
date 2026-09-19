"""Dashboard integrado."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.api.v1.routes._spec_params import spec_levels_from
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def dashboard(
    session: SessionDep,
    settings: SettingsDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon"),
    sell_location: str | None = Query(None),
    return_rate: float | None = Query(None, ge=0, le=1),
    station_fee_per_100_nutrition: float | None = Query(None, ge=0),
    # Especialização por família de recurso (0-100). Sem informar, a conta
    # assume spec 0 e a resposta avisa.
    spec_leather: int = Query(0, ge=0, le=100, description="Spec de couro."),
    spec_cloth: int = Query(0, ge=0, le=100, description="Spec de tecido."),
    spec_planks: int = Query(0, ge=0, le=100, description="Spec de tábuas."),
    spec_metalbar: int = Query(0, ge=0, le=100, description="Spec de barras."),
    spec_stoneblock: int = Query(0, ge=0, le=100, description="Spec de blocos."),
    setup_fee_pct: float | None = Query(None, ge=0, le=1),
    sales_tax_pct: float | None = Query(None, ge=0, le=1),
    premium: bool | None = Query(None),
    focus_budget: float | None = Query(None, ge=0),
    horizon_days: int = Query(7, ge=1, le=90),
) -> DashboardResponse:
    return await build_dashboard(
        session, settings,
        server=server,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        return_rate=return_rate,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        spec_levels=spec_levels_from(
            spec_leather, spec_cloth, spec_planks, spec_metalbar, spec_stoneblock
        ),
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        focus_budget=focus_budget,
        horizon_days=horizon_days,
    )
