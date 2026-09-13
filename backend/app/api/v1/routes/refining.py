"""Oportunidades de refino."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.schemas.refining import RefiningResponse
from app.services.refining_service import find_refining_opportunities

router = APIRouter(prefix="/refining", tags=["refining"])

SOURCING = {"MERCADO": Sourcing.MARKET, "PRODUZIR": Sourcing.CRAFT,
            "MAIS_BARATO": Sourcing.CHEAPEST}


@router.get("/opportunities", response_model=RefiningResponse)
async def refining_opportunities(
    session: SessionDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon"),
    sell_location: str | None = Query(None),
    # A escolha que define a resposta: quem compra tudo pronto usa MERCADO;
    # quem já tem a cadeia montada usa PRODUZIR. MAIS_BARATO decide tier a tier.
    sourcing: str = Query("MAIS_BARATO", description="MERCADO | PRODUZIR | MAIS_BARATO"),
    return_rate: float | None = Query(None, ge=0, le=1),
    station_fee: float | None = Query(None, ge=0),
    setup_fee_pct: float | None = Query(None, ge=0, le=1),
    sales_tax_pct: float | None = Query(None, ge=0, le=1),
    premium: bool | None = Query(None),
    family: str | None = Query(None, description="PLANKS, METALBAR, LEATHER, CLOTH, STONEBLOCK"),
    tier: int | None = Query(None, ge=2, le=8),
    strategy: str = Query("IMEDIATA"),
    limit: int = Query(40, ge=1, le=200),
) -> RefiningResponse:
    return await find_refining_opportunities(
        session,
        server=server,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        sourcing=SOURCING.get(sourcing.upper(), Sourcing.CHEAPEST),
        return_rate=return_rate,
        station_fee=station_fee,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        family=family,
        tier=tier,
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        limit=limit,
    )
