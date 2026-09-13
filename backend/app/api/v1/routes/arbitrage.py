"""Arbitragem entre cidades."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.calculations.fees import Strategy
from app.schemas.arbitrage import ArbitrageResponse
from app.services.arbitrage_service import find_arbitrage

router = APIRouter(prefix="/arbitrage", tags=["arbitrage"])


@router.get("", response_model=ArbitrageResponse)
async def arbitrage(
    session: SessionDep,
    server: str = Query("west"),
    strategy: str = Query("IMEDIATA", description="IMEDIATA | PACIENTE"),
    quantity: int = Query(100, ge=1, le=100_000),
    # Taxas do usuário. Sem elas, a resposta vem com economics.known = false e
    # o motivo explicando o que preencher — nunca um lucro calculado com taxa
    # zero, que seria sempre otimista.
    setup_fee_pct: float | None = Query(
        None, ge=0, le=1, description="Ex.: 0.025 para 2,5%. Vence a configuração do sistema."
    ),
    sales_tax_pct: float | None = Query(None, ge=0, le=1, description="Ex.: 0.04 para 4%."),
    premium: bool | None = Query(
        None, description="Conta com Premium. Define qual imposto padrão é usado."
    ),
    transport_cost_per_unit: float = Query(0.0, ge=0),
    max_age_seconds: int = Query(
        21_600, ge=60, description="Descarta pontas mais velhas que isto."
    ),
    include_black_market: bool = Query(
        False, description="Black Market tem semântica de ordens invertida e não validada."
    ),
    min_profit: float = Query(0.0),
    tracked_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
) -> ArbitrageResponse:
    escolhida = Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST

    return await find_arbitrage(
        session,
        server=server,
        strategy=escolhida,
        quantity=quantity,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        transport_cost_per_unit=transport_cost_per_unit,
        max_age_seconds=max_age_seconds,
        include_black_market=include_black_market,
        min_profit=min_profit,
        tracked_only=tracked_only,
        limit=limit,
    )
