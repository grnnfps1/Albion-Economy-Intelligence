"""Oportunidades de crafting.

Junta três coisas que vivem separadas: a receita (dump do jogo), o preço dos
materiais (mercado da cidade onde se compra) e o preço de venda do item final
(mercado da cidade onde se vende).

O cálculo em si é puro e mora em `calculations/crafting.py`. Aqui fica a
política: onde comprar, onde vender, o que descartar antes de calcular.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.crafting import MaterialCost, compute_craft
from app.calculations.fees import Strategy
from app.catalog.icons import item_icon_url
from app.repositories import market as market_repo
from app.repositories import recipes_repo, settings_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.schemas.crafting import (
    CraftEconomicsOut,
    CraftingResponse,
    CraftOpportunityOut,
    CraftParamsUsed,
    MaterialOut,
)
from app.services.arbitrage_service import resolve_fees

DATA_SOURCE_NOTE = (
    "Custos e receita vêm da coleta comunitária do AODP; as receitas vêm do dump "
    "oficial do jogo. Um material sem cotação torna o craft inteiro desconhecido: "
    "custo parcial não é custo menor."
)

RETURN_RATE_KEY = "crafting.return_rate.base"
STATION_FEE_KEY = "crafting.station_fee_formula"


def _age(value: datetime | None, now: datetime) -> int | None:
    return None if value is None else max(0, int((now - value).total_seconds()))


async def find_crafting_opportunities(
    session: AsyncSession,
    server: str,
    buy_location: str,
    sell_location: str,
    return_rate: float | None,
    station_fee: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    crafts: int,
    strategy: Strategy,
    sort_by: str,
    tier: int | None,
    station_category: str | None,
    limit: int,
) -> CraftingResponse:
    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)

    # Preferência do usuário vence a configuração; configuração vence nada.
    if return_rate is None:
        return_rate = await settings_repo.get_value(session, RETURN_RATE_KEY)
    if station_fee is None:
        station_fee = await settings_repo.get_value(session, STATION_FEE_KEY)

    faltando = list(resumo_taxas.missing)
    if return_rate is None:
        faltando.append("crafting.return_rate")
    if station_fee is None:
        faltando.append("crafting.station_fee")

    params = CraftParamsUsed(
        return_rate=return_rate,
        station_fee=station_fee,
        fees=resumo_taxas,
        complete=not faltando,
        missing=faltando,
    )

    receitas = await recipes_repo.list_recipes(
        session, station_category=station_category, tier=tier, tracked_only=True, limit=limit * 6
    )
    if not receitas:
        return _empty(server, buy_location, sell_location, crafts, sort_by, params)

    # Uma consulta de preços para tudo que interessa, em vez de uma por receita.
    ids = {r.output_item_id for r in receitas}
    for receita in receitas:
        ids.update(m.item_id for m in receita.materials)

    linhas, _ = await market_repo.search_prices(
        session,
        server_code=server,
        location_slugs=sorted({buy_location, sell_location}),
        limit=20_000,
    )
    precos: dict[tuple[int, str], tuple] = {}
    for price, item, location in linhas:
        # Qualidade 1 e 2 são as que interessam para material e craft normal;
        # fica com a primeira encontrada para não misturar qualidades no custo.
        chave = (item.id, location.slug)
        if chave not in precos:
            precos[chave] = (price, item, location)

    catalogo = await recipes_repo.load_items(session, sorted(ids))
    sinais = await liquidity_by_item_location(session, server, sorted(ids))

    now = datetime.now(UTC)
    resultados: list[CraftOpportunityOut] = []

    for receita in receitas:
        saida = catalogo.get(receita.output_item_id)
        if saida is None:
            continue

        venda = precos.get((saida.id, sell_location))
        sell_price = None
        sell_age = None
        if venda is not None:
            preco_venda = venda[0]
            # Estratégia imediata entrega para ordem de compra; paciente cria
            # ordem de venda. Preços e taxas diferentes.
            if strategy is Strategy.FAST:
                sell_price, sell_age = preco_venda.buy_price_max, _age(
                    preco_venda.buy_price_max_date, now
                )
            else:
                sell_price, sell_age = preco_venda.sell_price_min, _age(
                    preco_venda.sell_price_min_date, now
                )

        materiais: list[MaterialCost] = []
        materiais_out: list[MaterialOut] = []
        for material in receita.materials:
            item_material = catalogo.get(material.item_id)
            if item_material is None:
                continue
            compra = precos.get((material.item_id, buy_location))
            unit = compra[0].sell_price_min if compra else None
            idade = _age(compra[0].sell_price_min_date, now) if compra else None

            materiais.append(
                MaterialCost(
                    unique_name=item_material.unique_name,
                    display_name=item_material.display_name_pt
                    or item_material.display_name_en,
                    quantity=material.quantity,
                    unit_price=unit,
                    is_returnable=material.is_returnable,
                    location=compra[2].display_name if compra else None,
                    age_seconds=idade,
                )
            )
            materiais_out.append(
                MaterialOut(
                    item=item_material.unique_name,
                    item_name=item_material.display_name_pt or item_material.display_name_en,
                    icon_url=item_icon_url(item_material.unique_name),
                    quantity=material.quantity,
                    unit_price=unit,
                    total_price=None if unit is None else unit * material.quantity,
                    is_returnable=material.is_returnable,
                    location=compra[2].display_name if compra else None,
                    age_seconds=idade,
                )
            )

        economia = compute_craft(
            materials=materiais,
            sell_price=sell_price,
            fees=fees,
            return_rate=return_rate,
            station_fee=station_fee,
            output_quantity=receita.output_quantity,
            focus_cost=receita.focus_cost,
            crafts=crafts,
            strategy=strategy,
        )

        # Giro do item final no mercado onde se pretende vender.
        sinal = next(
            (
                valor
                for (item_id, _loc, _q), valor in sinais.items()
                if item_id == saida.id and valor.known
            ),
            None,
        )

        resultados.append(
            CraftOpportunityOut(
                item=saida.unique_name,
                item_name=saida.display_name_pt or saida.display_name_en,
                icon_url=item_icon_url(saida.unique_name),
                tier=saida.tier,
                enchantment=saida.enchantment,
                recipe_variant=receita.variant_index,
                station_category=receita.station_category,
                buy_location=buy_location,
                sell_location=sell_location,
                sell_price=sell_price,
                sell_age_seconds=sell_age,
                liquidity_units_per_day=sinal.units_per_day if sinal and sinal.known else None,
                materials=materiais_out,
                economics=CraftEconomicsOut(
                    known=economia.known,
                    reason=economia.reason,
                    output_quantity=economia.output_quantity,
                    focus_cost=economia.focus_cost,
                    material_cost_gross=economia.material_cost_gross,
                    material_cost_net=economia.material_cost_net,
                    returned_value=economia.returned_value,
                    station_fee=economia.station_fee,
                    sale_revenue_net=economia.sale_revenue_net,
                    market_fees=economia.market_fees,
                    profit=economia.profit,
                    margin_pct=economia.margin_pct,
                    roi_pct=economia.roi_pct,
                    profit_per_focus=economia.profit_per_focus,
                ),
            )
        )

    # Focus é o recurso escasso, não a prata: lucro absoluto alto com Focus alto
    # pode ser pior negócio. Por isso a ordenação padrão é por prata/focus.
    def chave(op: CraftOpportunityOut) -> float:
        if not op.economics.known:
            return float("-inf")
        if sort_by == "profit":
            return op.economics.profit or 0.0
        if sort_by == "roi":
            return op.economics.roi_pct or 0.0
        return op.economics.profit_per_focus if op.economics.profit_per_focus is not None else -1

    resultados.sort(key=chave, reverse=True)

    return CraftingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        crafts=crafts,
        sort_by=sort_by,
        total=len(resultados),
        params=params,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        opportunities=resultados[:limit],
    )


def _empty(server, buy_location, sell_location, crafts, sort_by, params) -> CraftingResponse:
    return CraftingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        crafts=crafts,
        sort_by=sort_by,
        total=0,
        params=params,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        opportunities=[],
    )
