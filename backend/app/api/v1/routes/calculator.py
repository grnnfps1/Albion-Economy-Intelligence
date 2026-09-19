"""Calculador de crafting: uma família por vez, todas as combinações.

Rota separada de `/crafting/opportunities` de propósito. São perguntas
diferentes: o ranking responde *onde gasto meu Focus hoje*; o calculador
responde *quanto rende esta família se eu mexer nos preços*. Fundir as duas
daria uma tela que responde mal as duas.
"""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.v1.routes._spec_params import (
    SPEC_ITEMS_DESC,
    item_levels_from,
    spec_levels_from,
)
from app.schemas.calculator import CalculatorResponse
from app.services.calculator_service import FAMILIES, build_calculator
from app.services.sourcing import SourcingMode

router = APIRouter(prefix="/crafting", tags=["crafting"])

SOURCING_MODE = {
    "CIDADE_UNICA": SourcingMode.SINGLE_CITY,
    "MAIS_BARATO": SourcingMode.CHEAPEST,
    "COMPARAR": SourcingMode.COMPARE,
}


@router.get("/calculator", response_model=CalculatorResponse)
async def calculator(
    session: SessionDep,
    user_id: UserDep,
    server: str = Query("west"),
    family: str = Query(
        FAMILIES[0], description=f"Uma de {FAMILIES}. Pedra tem 7 linhas; as outras, 27."
    ),
    buy_location: str = Query("caerleon"),
    sell_location: str | None = Query(None, description="padrão: a mesma da compra"),
    quantity: int = Query(
        1,
        ge=1,
        le=100_000,
        description=(
            "Quantas unidades você quer produzir. O padrão é **1**: a base da "
            "tabela é a unidade, e este campo escala tudo que é extensivo. As "
            "razões (margem, ROI, prata/focus) não mudam com ele — há teste."
        ),
    ),
    # A taxa de retorno **não** é campo livre: ela vem da matriz da fase 14, e o
    # que o usuário escolhe é a cidade e se usa Focus. Um campo aberto convida a
    # digitar errado um número que o sistema já sabe. `return_rate` continua
    # aceito como sobrescrita explícita, para o caso atípico.
    return_rate: float | None = Query(
        None, ge=0, le=1, description="Sobrescreve a matriz. Use só se a sua situação for atípica."
    ),
    use_focus: bool = Query(False, description="Entra como +59% em B."),
    produce_on_island: bool = Query(
        False,
        description=(
            "Produzir na ilha. A ilha nao tem a base de cidade: 0% de retorno "
            "sem Focus, 37,1% com. E escolha de onde produzir, nao de onde "
            "comprar -- ilha nao tem mercado."
        ),
    ),
    daily_production_bonus: float = Query(0, ge=0, le=1),
    station_fee_per_100_nutrition: float | None = Query(None, ge=0),
    setup_fee_pct: float | None = Query(None, ge=0, le=1),
    sales_tax_pct: float | None = Query(None, ge=0, le=1),
    premium: bool | None = Query(None),
    spec_leather: int = Query(0, ge=0, le=100),
    spec_cloth: int = Query(0, ge=0, le=100),
    spec_planks: int = Query(0, ge=0, le=100),
    spec_metalbar: int = Query(0, ge=0, le=100),
    spec_stoneblock: int = Query(0, ge=0, le=100),
    spec_items: str | None = Query(None, description=SPEC_ITEMS_DESC),
    focus_per_day: float | None = Query(None, ge=0),
    sourcing_mode: str = Query("CIDADE_UNICA"),
) -> CalculatorResponse:
    return await build_calculator(
        session,
        server=server,
        family=family,
        buy_location=buy_location,
        sell_location=sell_location or buy_location,
        quantity=quantity,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        return_rate=return_rate,
        use_focus=use_focus,
        daily_production_bonus=daily_production_bonus,
        produce_on_island=produce_on_island,
        spec_levels=spec_levels_from(
            spec_leather, spec_cloth, spec_planks, spec_metalbar, spec_stoneblock
        ),
        spec_item_levels=item_levels_from(spec_items),
        focus_per_day=focus_per_day,
        user_id=user_id,
        sourcing_mode=SOURCING_MODE.get(sourcing_mode.upper(), SourcingMode.SINGLE_CITY),
    )
