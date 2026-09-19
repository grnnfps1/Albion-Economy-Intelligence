"""Dashboard.

Integra as cinco telas numa só e responde "o que eu faço agora?".

O risco desta tela é virar vitrine: mostrar o maior número de cada categoria sem
o contexto que o torna confiável seria um retrocesso em relação a tudo que as
telas de origem constroem. Por isso cada card carrega idade do dado, confiança e
liquidez — e o estado do pipeline vem **antes** dos números, porque se a coleta
parou todos eles estão olhando um retrato antigo.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.chain import Sourcing
from app.calculations.fees import Strategy
from app.core.config import Settings
from app.core.freshness import Freshness, classify, data_age_seconds
from app.models.market import MarketPrice
from app.models.reference import Server
from app.repositories import observability as obs_repo
from app.schemas.dashboard import DashboardCard, DashboardResponse, PipelineHealth
from app.services.arbitrage_service import find_arbitrage
from app.services.crafting_service import find_crafting_opportunities
from app.services.focus_service import build_focus_ranking
from app.services.refining_service import find_refining_opportunities

DATA_SOURCE_NOTE = (
    "Cada card mostra a idade do dado que o sustenta. Um número grande sobre "
    "cotação de ontem não é oportunidade: é retrato antigo."
)


async def _pipeline(session: AsyncSession, settings: Settings, server: str) -> PipelineHealth:
    now = datetime.now(UTC)

    total = await session.scalar(
        select(func.count())
        .select_from(MarketPrice)
        .join(Server, MarketPrice.server_id == Server.id)
        .where(Server.code == server)
    )
    ultima = await session.scalar(
        select(func.max(MarketPrice.observed_at))
        .join(Server, MarketPrice.server_id == Server.id)
        .where(Server.code == server)
    )
    limite = now.timestamp() - settings.freshness_stale_seconds
    velhos = await session.scalar(
        select(func.count())
        .select_from(MarketPrice)
        .join(Server, MarketPrice.server_id == Server.id)
        .where(
            Server.code == server,
            MarketPrice.observed_at < datetime.fromtimestamp(limite, UTC),
        )
    )

    idade = data_age_seconds(ultima, now)
    execucao = await obs_repo.last_run(session, "market")

    return PipelineHealth(
        prices_tracked=int(total or 0),
        last_collection_age_seconds=idade,
        freshness=classify(
            idade, settings.freshness_fresh_seconds, settings.freshness_stale_seconds
        ),
        last_run_status=execucao.status if execucao else None,
        stale_price_ratio=round((velhos or 0) / total, 3) if total else None,
    )


def _indisponivel(kind: str, href: str, reason: str) -> DashboardCard:
    return DashboardCard(kind=kind, available=False, reason=reason, href=href)


async def build_dashboard(
    session: AsyncSession,
    settings: Settings,
    server: str,
    buy_location: str,
    sell_location: str,
    return_rate: float | None,
    station_fee_per_100_nutrition: float | None,
    spec_levels: dict[str, int] | None,
    spec_item_levels: dict[str, int] | None,
    focus_per_day: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    focus_budget: float | None,
    horizon_days: int,
) -> DashboardResponse:
    now = datetime.now(UTC)
    pipeline = await _pipeline(session, settings, server)

    comum = dict(
        server=server, buy_location=buy_location, sell_location=sell_location,
        return_rate=return_rate,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        spec_levels=spec_levels,
        spec_item_levels=spec_item_levels,
        focus_per_day=focus_per_day,
        setup_fee_pct=setup_fee_pct, sales_tax_pct=sales_tax_pct, premium=premium,
        strategy=Strategy.FAST,
    )

    arbitragem = await find_arbitrage(
        session, server=server, strategy=Strategy.FAST, quantity=100,
        setup_fee_pct=setup_fee_pct, sales_tax_pct=sales_tax_pct, premium=premium,
        transport_cost_per_unit=0.0, max_age_seconds=settings.freshness_stale_seconds,
        # Destino validado na fase 13: ele preenche buy_price_max sempre, e a
        # orientação é normal (docs/02-aodp.md).
        include_black_market=True, min_profit=1.0, tracked_only=True, limit=10,
    )
    craft = await find_crafting_opportunities(
        session, **comum, crafts=1, sort_by="profit_per_focus",
        tier=None, station_category=None, limit=10,
    )
    refino = await find_refining_opportunities(
        session, **comum, sourcing=Sourcing.CHEAPEST, family=None, tier=None, limit=10,
    )
    focus = await build_focus_ranking(
        session, server=server, buy_location=buy_location, sell_location=sell_location,
        focus_budget=focus_budget, horizon_days=horizon_days,
        return_rate=return_rate,
        station_fee_per_100_nutrition=station_fee_per_100_nutrition,
        spec_levels=spec_levels,
        spec_item_levels=spec_item_levels,
        focus_per_day=focus_per_day,
        setup_fee_pct=setup_fee_pct, sales_tax_pct=sales_tax_pct, premium=premium,
        sourcing=Sourcing.CHEAPEST, strategy=Strategy.FAST,
        sort_by="realizable_profit", limit=10,
    )

    def frescor(idade: int | None) -> Freshness:
        return classify(
            idade, settings.freshness_fresh_seconds, settings.freshness_stale_seconds
        )

    cards: list[DashboardCard] = []

    melhor_arb = next(
        (op for op in arbitragem.opportunities if op.economics.known), None
    )
    if melhor_arb is None:
        cards.append(
            _indisponivel(
                "ARBITRAGEM", "/arbitrage",
                "taxas não configuradas" if not arbitragem.fees.complete
                else "nenhuma rota viável agora",
            )
        )
    else:
        cards.append(
            DashboardCard(
                kind="ARBITRAGEM", available=True,
                item=melhor_arb.item, item_name=melhor_arb.item_name,
                icon_url=melhor_arb.icon_url, tier=melhor_arb.tier,
                headline=melhor_arb.economics.net_profit,
                headline_label="lucro em 100 un",
                detail=f"{melhor_arb.origin} → {melhor_arb.destination}",
                age_seconds=melhor_arb.worst_age_seconds,
                freshness=frescor(melhor_arb.worst_age_seconds),
                score=melhor_arb.score.value,
                confidence=melhor_arb.score.confidence,
                liquidity_units_per_day=melhor_arb.liquidity_units_per_day,
                href="/arbitrage",
            )
        )

    melhor_craft = next((op for op in craft.opportunities if op.economics.known), None)
    if melhor_craft is None:
        cards.append(
            _indisponivel(
                "CRAFTING", "/crafting",
                "parâmetros não configurados" if not craft.params.complete
                else "sem receita com dados suficientes",
            )
        )
    else:
        cards.append(
            DashboardCard(
                kind="CRAFTING", available=True,
                item=melhor_craft.item, item_name=melhor_craft.item_name,
                icon_url=melhor_craft.icon_url, tier=melhor_craft.tier,
                headline=melhor_craft.economics.profit_per_focus,
                headline_label="prata por focus",
                detail=f"{melhor_craft.economics.focus_cost} focus · "
                f"{len(melhor_craft.materials)} materiais",
                age_seconds=melhor_craft.sell_age_seconds,
                freshness=frescor(melhor_craft.sell_age_seconds),
                liquidity_units_per_day=melhor_craft.liquidity_units_per_day,
                href="/crafting",
            )
        )

    melhor_refino = next((op for op in refino.opportunities if op.known), None)
    if melhor_refino is None:
        cards.append(
            _indisponivel(
                "REFINO", "/refining",
                "parâmetros não configurados" if not refino.params.complete
                else "sem cadeia com dados suficientes",
            )
        )
    else:
        economia = (
            melhor_refino.cost_from_market - melhor_refino.cost_from_crafting
            if melhor_refino.cost_from_market is not None
            and melhor_refino.cost_from_crafting is not None
            else None
        )
        cards.append(
            DashboardCard(
                kind="REFINO", available=True,
                item=melhor_refino.item, item_name=melhor_refino.item_name,
                icon_url=melhor_refino.icon_url, tier=melhor_refino.tier,
                headline=melhor_refino.profit,
                headline_label="lucro por unidade",
                detail=(
                    f"produzir economiza {economia:,.0f} por unidade"
                    if economia and economia > 0
                    else "comprar o insumo sai mais barato"
                ),
                age_seconds=melhor_refino.sell_age_seconds,
                freshness=frescor(melhor_refino.sell_age_seconds),
                liquidity_units_per_day=melhor_refino.liquidity_units_per_day,
                href="/refining",
            )
        )

    melhor_focus = focus.plans[0] if focus.plans else None
    if melhor_focus is None:
        cards.append(
            _indisponivel(
                "FOCUS", "/focus",
                "parâmetros não configurados" if not focus.params.complete
                else "sem operação com focus e dados suficientes",
            )
        )
    else:
        cards.append(
            DashboardCard(
                kind="FOCUS", available=True,
                item=melhor_focus.item, item_name=melhor_focus.item_name,
                icon_url=melhor_focus.icon_url, tier=melhor_focus.tier,
                headline=melhor_focus.realizable_profit,
                headline_label=f"ganho em {horizon_days} d",
                detail=f"{melhor_focus.route.lower()} · {melhor_focus.limiter.lower()}",
                liquidity_units_per_day=melhor_focus.liquidity_units_per_day,
                href="/focus",
            )
        )

    # Top oportunidades: só arbitragem tem score comparável hoje. Misturar
    # categorias sem uma métrica comum produziria um ranking que não significa
    # nada -- melhor mostrar menos e verdadeiro.
    top = [
        DashboardCard(
            kind="ARBITRAGEM", available=True,
            item=op.item, item_name=op.item_name, icon_url=op.icon_url, tier=op.tier,
            headline=op.economics.net_profit, headline_label="lucro em 100 un",
            detail=f"{op.origin} → {op.destination}",
            age_seconds=op.worst_age_seconds, freshness=frescor(op.worst_age_seconds),
            score=op.score.value, confidence=op.score.confidence,
            liquidity_units_per_day=op.liquidity_units_per_day, href="/arbitrage",
        )
        for op in arbitragem.opportunities
        if op.economics.known and op.score.value is not None
    ][:8]

    return DashboardResponse(
        server=server,
        generated_at=now.isoformat(),
        pipeline=pipeline,
        params=craft.params,
        cards=cards,
        top_opportunities=top,
        data_source_note=DATA_SOURCE_NOTE,
    )
