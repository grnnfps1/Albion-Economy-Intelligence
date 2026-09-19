"""Ranking unificado de Focus.

Junta crafting e refino numa lista só e responde a pergunta prática: **onde
gastar o Focus de hoje?**

A diferença em relação às telas anteriores é que aqui a taxa não basta. Prata por
Focus é um rendimento por ponto gasto; o que se leva para casa é limitado pelo
Focus que se tem e pelo que o mercado consegue absorver. Uma operação com taxa
menor mas líquida costuma render mais na prática.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.calculations.focus import FocusCandidate, Route, build_ranking
from app.catalog.icons import item_icon_url
from app.models.catalog import Item
from app.schemas.focus import FocusPlanOut, FocusResponse
from app.services.crafting_service import find_crafting_opportunities
from app.services.refining_service import find_refining_opportunities

DATA_SOURCE_NOTE = (
    "Prata por Focus é uma taxa, não um ganho. O ranking cruza a taxa com o Focus "
    "disponível e com o giro do item: escoar 5.000 unidades de algo que gira 3 por "
    "dia leva anos, e a margem evapora antes disso."
)


async def build_focus_ranking(
    session: AsyncSession,
    server: str,
    buy_location: str,
    sell_location: str,
    focus_budget: float | None,
    horizon_days: int,
    return_rate: float | None,
    station_fee_per_100_nutrition: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    sourcing: Sourcing,
    strategy: Strategy,
    sort_by: str,
    limit: int,
) -> FocusResponse:
    comum = dict(
        server=server, buy_location=buy_location, sell_location=sell_location,
        return_rate=return_rate,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        setup_fee_pct=setup_fee_pct, sales_tax_pct=sales_tax_pct, premium=premium,
        strategy=strategy,
    )

    craft = await find_crafting_opportunities(
        session, **comum, crafts=1, sort_by="profit_per_focus",
        tier=None, station_category=None, limit=200,
    )
    refino = await find_refining_opportunities(
        session, **comum, sourcing=sourcing, family=None, tier=None, limit=200,
    )

    candidatos: list[FocusCandidate] = []
    liquidez: dict[str, float | None] = {}

    for op in craft.opportunities:
        eco = op.economics
        if not eco.known or eco.profit is None or eco.focus_cost <= 0:
            continue
        unidades = max(1, eco.output_quantity)
        candidatos.append(
            FocusCandidate(
                item=op.item,
                route=Route.CRAFT,
                profit_per_unit=eco.profit / unidades,
                focus_per_unit=eco.focus_cost / unidades,
                liquidity_units_per_day=op.liquidity_units_per_day,
            )
        )
        liquidez[op.item] = op.liquidity_units_per_day

    for op in refino.opportunities:
        if not op.known or op.profit is None or op.focus_per_unit <= 0:
            continue
        candidatos.append(
            FocusCandidate(
                item=op.item,
                route=Route.REFINE,
                profit_per_unit=op.profit,
                focus_per_unit=op.focus_per_unit,
                liquidity_units_per_day=op.liquidity_units_per_day,
            )
        )
        liquidez.setdefault(op.item, op.liquidity_units_per_day)

    planos = build_ranking(candidatos, focus_budget, horizon_days, sort_by)

    nomes = [plano.item for plano in planos[:limit]]
    catalogo: dict[str, Item] = {}
    if nomes:
        rows = await session.scalars(select(Item).where(Item.unique_name.in_(nomes)))
        catalogo = {item.unique_name: item for item in rows.all()}

    saida = []
    for plano in planos[:limit]:
        item = catalogo.get(plano.item)
        saida.append(
            FocusPlanOut(
                item=plano.item,
                item_name=(item.display_name_pt or item.display_name_en) if item else None,
                icon_url=item_icon_url(plano.item),
                tier=item.tier if item else None,
                enchantment=item.enchantment if item else 0,
                route=str(plano.route),
                profit_per_unit=plano.profit_per_unit,
                focus_per_unit=plano.focus_per_unit,
                profit_per_focus=plano.profit_per_focus,
                units_by_focus=plano.units_by_focus,
                units_by_liquidity=plano.units_by_liquidity,
                units=plano.units,
                focus_used=plano.focus_used,
                realizable_profit=plano.realizable_profit,
                limiter=str(plano.limiter),
                days_to_sell=plano.days_to_sell,
                liquidity_units_per_day=liquidez.get(plano.item),
            )
        )

    return FocusResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        focus_budget=focus_budget,
        horizon_days=horizon_days,
        sort_by=sort_by,
        total=len(planos),
        # Os parâmetros são os mesmos das duas telas de origem; basta reportar um.
        params=craft.params,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        plans=saida,
    )
