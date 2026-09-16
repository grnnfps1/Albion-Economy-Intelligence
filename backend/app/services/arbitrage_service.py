"""Orquestração da arbitragem."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.fees import FeeProfile, Strategy
from app.catalog.icons import item_icon_url
from app.opportunities.arbitrage import ArbitrageOpportunity, PriceRow, build_opportunities
from app.repositories import market as market_repo
from app.repositories import settings_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.schemas.arbitrage import (
    ArbitrageResponse,
    EconomicsOut,
    FeesUsed,
    OpportunityOut,
    ScoreOut,
)
from app.services.risk_service import load_route_zones, resolve_risk, risk_out

DATA_SOURCE_NOTE = (
    "Oportunidades calculadas sobre coleta comunitária do Albion Online Data Project. "
    "A idade exibida é a da ponta mais velha: a operação só é tão confiável quanto o "
    "pior dos dois preços."
)

FEE_KEYS = [
    "market.sell_order_setup_fee_pct",
    "market.sales_tax_pct.premium",
    "market.sales_tax_pct.standard",
]
WEIGHTS_KEY = "score.weights"


async def resolve_fees(
    session: AsyncSession,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
) -> tuple[FeeProfile, FeesUsed]:
    """Preferência do usuário vence a configuração do sistema.

    O imposto depende de a conta ter Premium, então um valor fixo de servidor
    mostraria lucro errado para metade das pessoas. Quando o usuário informa,
    usamos o dele; senão, caímos no banco; se o banco não tiver, fica UNKNOWN.
    """
    origem = "usuario"

    if setup_fee_pct is None or sales_tax_pct is None:
        configurado = await settings_repo.get_values(session, FEE_KEYS)
        if setup_fee_pct is None:
            setup_fee_pct = configurado.get("market.sell_order_setup_fee_pct")
        if sales_tax_pct is None:
            chave = (
                "market.sales_tax_pct.premium" if premium else "market.sales_tax_pct.standard"
            )
            sales_tax_pct = configurado.get(chave)
        origem = "config" if (setup_fee_pct is not None or sales_tax_pct is not None) else "UNKNOWN"

    profile = FeeProfile(
        setup_fee_pct=setup_fee_pct, sales_tax_pct=sales_tax_pct, premium=premium
    )
    resumo = FeesUsed(
        setup_fee_pct=setup_fee_pct,
        sales_tax_pct=sales_tax_pct,
        premium=premium,
        source=origem if profile.complete else "UNKNOWN",
        complete=profile.complete,
        missing=profile.missing(),
    )
    return profile, resumo


DEFAULT_WEIGHTS = {
    "profit": 0.25, "margin": 0.20, "roi": 0.15,
    "freshness": 0.15, "liquidity": 0.15, "trend": 0.05,
    # Previstos em config_parameters desde a fase 0 e sem uso até agora: risco
    # vem da preferência do usuário, distância vem da zona da rota.
    "risk": 0.02, "distance": 0.03,
}



async def find_arbitrage(
    session: AsyncSession,
    server: str,
    strategy: Strategy,
    quantity: int,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    transport_cost_per_unit: float,
    max_age_seconds: int,
    include_black_market: bool,
    min_profit: float,
    tracked_only: bool,
    limit: int,
    loss_pct_blue: float | None = None,
    loss_pct_red_black: float | None = None,
) -> ArbitrageResponse:
    fees, resumo = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
    perfil_risco, resumo_risco = await resolve_risk(session, loss_pct_blue, loss_pct_red_black)
    zonas = await load_route_zones(session)

    weights = await settings_repo.get_value(session, WEIGHTS_KEY, DEFAULT_WEIGHTS)

    linhas, _total = await market_repo.search_prices(
        session, server_code=server, tracked_only=tracked_only, limit=5000
    )
    sinais = await liquidity_by_item_location(
        session, server, [item.id for _p, item, _l in linhas]
    )

    rows = [
        PriceRow(price, item, location, sinais.get((item.id, location.id, price.quality)))
        for price, item, location in linhas
    ]

    encontradas = build_opportunities(
        rows,
        now=datetime.now(UTC),
        fees=fees,
        weights=weights,
        strategy=strategy,
        quantity=quantity,
        transport_cost_per_unit=transport_cost_per_unit,
        max_age_seconds=max_age_seconds,
        include_black_market=include_black_market,
        min_profit=min_profit,
        zone_of=zonas.of,
        risk=perfil_risco,
    )

    return ArbitrageResponse(
        server=server,
        strategy=str(strategy),
        quantity=quantity,
        total=len(encontradas),
        fees=resumo,
        risk=resumo_risco,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        opportunities=[_to_out(op) for op in encontradas[:limit]],
    )


def _to_out(op: ArbitrageOpportunity) -> OpportunityOut:
    return OpportunityOut(
        item=op.item.unique_name,
        item_name=op.item.display_name_pt or op.item.display_name_en,
        icon_url=item_icon_url(op.item.unique_name, op.quality),
        tier=op.item.tier,
        enchantment=op.item.enchantment,
        quality=op.quality,
        strategy=str(op.strategy),
        origin=op.origin.display_name,
        origin_slug=op.origin.slug,
        destination=op.destination.display_name,
        destination_slug=op.destination.slug,
        buy_price=op.buy_price,
        sell_price=op.sell_price,
        # Spread bruto, antes de qualquer taxa. Vai rotulado como bruto na UI:
        # é o número que engana quando mostrado sozinho.
        spread_pct=round((op.sell_price - op.buy_price) / op.buy_price * 100, 2),
        worst_age_seconds=op.worst_age_seconds,
        liquidity_units_per_day=op.liquidity_units_per_day,
        economics=EconomicsOut(
            known=op.economics.known,
            reason=op.economics.reason,
            quantity=op.economics.quantity,
            unit_cost=op.economics.unit_cost,
            investment=op.economics.investment,
            gross_revenue=op.economics.gross_revenue,
            fees=op.economics.fees,
            transport_cost=op.economics.transport_cost,
            net_profit=op.economics.net_profit,
            margin_pct=op.economics.margin_pct,
            roi_pct=op.economics.roi_pct,
        ),
        risk=risk_out(op.risk),
        score=ScoreOut(
            value=op.score.score,
            band=op.score.band,
            confidence=op.score.confidence,
            components=op.score.components,
            missing=op.score.missing,
        ),
    )
