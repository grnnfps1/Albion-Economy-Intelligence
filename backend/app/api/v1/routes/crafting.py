"""Oportunidades de crafting."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.api.v1.routes._spec_params import spec_levels_from
from app.calculations.fees import Strategy
from app.schemas.crafting import CraftingResponse
from app.services.crafting_service import find_crafting_opportunities
from app.services.sourcing import SourcingMode

router = APIRouter(prefix="/crafting", tags=["crafting"])

ORDENACOES = ("profit_per_focus", "profit", "roi")

SOURCING_MODE = {
    "CIDADE_UNICA": SourcingMode.SINGLE_CITY,
    "MAIS_BARATO": SourcingMode.CHEAPEST,
    "COMPARAR": SourcingMode.COMPARE,
}



@router.get("/opportunities", response_model=CraftingResponse)
async def crafting_opportunities(
    session: SessionDep,
    server: str = Query("west"),
    buy_location: str = Query("caerleon", description="slug da cidade onde comprar material"),
    sell_location: str | None = Query(
        None,
        description=(
            "padrão: mesma cidade da compra. Aceita black-market como destino: ele "
            "compra equipamento, nunca recurso (docs/02-aodp.md)."
        ),
    ),
    # Nenhum destes é fato fixo. Retorno muda com Focus e especialização, taxa
    # de estação muda por cidade e por hora, imposto muda com Premium.
    return_rate: float | None = Query(
        None, ge=0, le=1,
        description="Sobrescreve a matriz. Ex.: 0.15 para 15%.",
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
    crafts: int = Query(1, ge=1, le=10_000),
    strategy: str = Query("IMEDIATA", description="IMEDIATA | PACIENTE"),
    sort_by: str = Query("profit_per_focus", description=f"um de {ORDENACOES}"),
    tier: int | None = Query(None, ge=1, le=8),
    station_category: str | None = Query(None, description="Ex.: wood, metal, cloth."),
    # Em qual cidade comprar cada material. CIDADE_UNICA é o padrão porque uma
    # rota espalhada custa viagem: só vale quando a economia paga o desvio.
    sourcing_mode: str = Query(
        "CIDADE_UNICA", description="CIDADE_UNICA | MAIS_BARATO | COMPARAR"
    ),
    # Probabilidade de perder a carga na rota. Preferência do usuário, como as
    # taxas, mas com padrão ZERO em vez de UNKNOWN: zero significa "não estou
    # modelando perda", e o lucro ajustado sai igual ao bruto, à vista.
    loss_pct_blue: float | None = Query(
        None, ge=0, le=1, description="Perda esperada entre cidades reais. Ex.: 0.01 para 1%."
    ),
    loss_pct_red_black: float | None = Query(
        None, ge=0, le=1,
        description="Perda esperada em rota por Caerleon ou Black Market. Ex.: 0.15 para 15%.",
    ),
    # O retorno sai da matriz por (cidade, atividade, Focus). `return_rate`
    # continua aceito, mas agora como sobrescrita.
    use_focus: bool = Query(False, description="Focus ligado muda a coluna da matriz."),
    daily_production_bonus: float = Query(
        0.0, ge=0, le=1, description="Bônus diário de produção: 0, 0.10 ou 0.20."
    ),
    limit: int = Query(30, ge=1, le=100),
) -> CraftingResponse:
    return await find_crafting_opportunities(
        session,
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
        crafts=crafts,
        strategy=Strategy.PATIENT if strategy.upper().startswith("PAC") else Strategy.FAST,
        sort_by=sort_by if sort_by in ORDENACOES else "profit_per_focus",
        tier=tier,
        station_category=station_category,
        sourcing_mode=SOURCING_MODE.get(sourcing_mode.upper(), SourcingMode.SINGLE_CITY),
        loss_pct_blue=loss_pct_blue,
        loss_pct_red_black=loss_pct_red_black,
        use_focus=use_focus,
        daily_production_bonus=daily_production_bonus,
        limit=limit,
    )
