"""Oportunidades de refino."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.api.v1.routes._spec_params import spec_levels_from
from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.schemas.refining import RefiningResponse
from app.services.refining_service import find_refining_opportunities
from app.services.sourcing import SourcingMode

router = APIRouter(prefix="/refining", tags=["refining"])

# Duas escolhas independentes, e o nome parecido engana: `sourcing` decide se
# o insumo do tier anterior é comprado ou produzido; `sourcing_mode` decide em
# qual cidade é comprado o que for comprado.
SOURCING = {"MERCADO": Sourcing.MARKET, "PRODUZIR": Sourcing.CRAFT,
            "MAIS_BARATO": Sourcing.CHEAPEST}

SOURCING_MODE = {
    "CIDADE_UNICA": SourcingMode.SINGLE_CITY,
    "MAIS_BARATO": SourcingMode.CHEAPEST,
    "COMPARAR": SourcingMode.COMPARE,
}



@router.get("/opportunities", response_model=RefiningResponse)
async def refining_opportunities(
    session: SessionDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon"),
    sell_location: str | None = Query(None),
    # A escolha que define a resposta: quem compra tudo pronto usa MERCADO;
    # quem já tem a cadeia montada usa PRODUZIR. MAIS_BARATO decide tier a tier.
    sourcing: str = Query("MAIS_BARATO", description="MERCADO | PRODUZIR | MAIS_BARATO"),
    return_rate: float | None = Query(
        None, ge=0, le=1, description="Sobrescreve a matriz de retorno."
    ),
    station_fee_per_100_nutrition: float | None = Query(
        None, ge=0,
        description=(
            "Prata por 100 de nutrição que a estação cobra — o número que "
            "aparece na tela da estação. A taxa de cada item sai dele: "
            "nutrição = item value × 0,1125."
        ),
    ),
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
    family: str | None = Query(None, description="PLANKS, METALBAR, LEATHER, CLOTH, STONEBLOCK"),
    tier: int | None = Query(None, ge=2, le=8),
    strategy: str = Query("IMEDIATA"),
    sourcing_mode: str = Query(
        "CIDADE_UNICA", description="CIDADE_UNICA | MAIS_BARATO | COMPARAR"
    ),
    # O retorno sai da matriz por (cidade, atividade, Focus). `return_rate`
    # continua aceito, mas agora como sobrescrita.
    use_focus: bool = Query(False, description="Focus ligado muda a coluna da matriz."),
    daily_production_bonus: float = Query(
        0.0, ge=0, le=1, description="Bônus diário de produção: 0, 0.10 ou 0.20."
    ),
    limit: int = Query(40, ge=1, le=200),
) -> RefiningResponse:
    return await find_refining_opportunities(
        session,
        server=server,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        sourcing=SOURCING.get(sourcing.upper(), Sourcing.CHEAPEST),
        return_rate=return_rate,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        spec_levels=spec_levels_from(
            spec_leather, spec_cloth, spec_planks, spec_metalbar, spec_stoneblock
        ),
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        family=family,
        tier=tier,
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        sourcing_mode=SOURCING_MODE.get(sourcing_mode.upper(), SourcingMode.SINGLE_CITY),
        use_focus=use_focus,
        daily_production_bonus=daily_production_bonus,
        limit=limit,
    )
