"""Oportunidades de refino.

Refino é crafting com uma diferença estrutural: a receita consome o recurso
bruto **e o refinado do tier anterior**. Isso transforma a pergunta. Não é "vale
refinar T5?" e sim "onde na cadeia T2→T8 está o gargalo de preço?".

Por isso a tela compara as duas formas de custear o insumo anterior — comprar
pronto ou produzir — em vez de escolher uma por conta própria.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.chain import RecipeSpec, Sourcing, resolve_unit_cost
from app.calculations.fees import Strategy, compute_trade
from app.catalog.icons import item_icon_url
from app.models.catalog import Item
from app.models.recipes import Recipe
from app.repositories import market as market_repo
from app.repositories import recipes_repo, settings_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.schemas.crafting import CraftParamsUsed
from app.schemas.refining import ChainStepOut, RefiningOut, RefiningResponse
from app.services.arbitrage_service import resolve_fees
from app.services.crafting_service import RETURN_RATE_KEY, STATION_FEE_KEY

DATA_SOURCE_NOTE = (
    "Cada elo da cadeia paga a taxa da estação, não só o último. Comprar o insumo "
    "do tier anterior e produzi-lo são respostas diferentes, e as duas estão "
    "certas dependendo de quem pergunta."
)

_FAMILIA = re.compile(r"^T\d_([A-Z]+?)(?:_LEVEL\d+)?(?:@\d)?$")

# Subcategoria que marca recurso refinado no dump.
REFINED_SUBCATEGORY = "refinedresources"


def family_of(unique_name: str) -> str | None:
    match = _FAMILIA.match(unique_name)
    return match.group(1) if match else None


def _age(value: datetime | None, now: datetime) -> int | None:
    return None if value is None else max(0, int((now - value).total_seconds()))


async def find_refining_opportunities(
    session: AsyncSession,
    server: str,
    buy_location: str,
    sell_location: str,
    sourcing: Sourcing,
    return_rate: float | None,
    station_fee: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    family: str | None,
    tier: int | None,
    strategy: Strategy,
    limit: int,
) -> RefiningResponse:
    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
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
        return_rate=return_rate, station_fee=station_fee, fees=resumo_taxas,
        complete=not faltando, missing=faltando,
    )

    # Só recursos refinados: é o que forma cadeia.
    refinados = list(
        (
            await session.scalars(
                select(Item)
                .where(
                    Item.subcategory_code == REFINED_SUBCATEGORY,
                    Item.active.is_(True),
                    *( [Item.tier == tier] if tier is not None else [] ),
                )
                .order_by(Item.base_name, Item.tier, Item.enchantment)
            )
        ).all()
    )
    if family:
        refinados = [item for item in refinados if family_of(item.unique_name) == family.upper()]

    if not refinados:
        return _vazio(server, buy_location, sell_location, sourcing, params, [])

    # Carrega tudo de uma vez: receitas, preços e liquidez.
    todas = await recipes_repo.list_recipes(session, tracked_only=False, limit=50_000)
    receitas: dict[int, Recipe] = {}
    for receita in todas:
        receitas.setdefault(receita.output_item_id, receita)

    ids = {item.id for item in refinados}
    for receita in receitas.values():
        ids.update(m.item_id for m in receita.materials)
        ids.add(receita.output_item_id)

    linhas, _ = await market_repo.search_prices(
        session, server_code=server,
        location_slugs=sorted({buy_location, sell_location}), limit=50_000,
    )
    precos_compra: dict[str, int] = {}
    precos_venda: dict[str, tuple[int | None, int | None]] = {}
    now = datetime.now(UTC)
    for price, item, location in linhas:
        if location.slug == buy_location and price.sell_price_min is not None:
            precos_compra.setdefault(item.unique_name, price.sell_price_min)
        if location.slug == sell_location:
            if strategy is Strategy.FAST:
                precos_venda.setdefault(
                    item.unique_name, (price.buy_price_max, _age(price.buy_price_max_date, now))
                )
            else:
                precos_venda.setdefault(
                    item.unique_name, (price.sell_price_min, _age(price.sell_price_min_date, now))
                )

    catalogo = await recipes_repo.load_items(session, sorted(ids))
    por_nome = {item.unique_name: item for item in catalogo.values()}
    sinais = await liquidity_by_item_location(session, server, sorted(ids))

    def receita_de(unique_name: str) -> RecipeSpec | None:
        item = por_nome.get(unique_name)
        if item is None:
            return None
        receita = receitas.get(item.id)
        if receita is None:
            return None
        materiais = tuple(
            (catalogo[m.item_id].unique_name, m.quantity, m.is_returnable)
            for m in receita.materials
            if m.item_id in catalogo
        )
        return RecipeSpec(receita.output_quantity, receita.focus_cost, materiais)

    resultados: list[RefiningOut] = []
    for item in refinados:
        cadeia = resolve_unit_cost(
            item.unique_name, sourcing, precos_compra.get, receita_de,
            return_rate, station_fee,
        )
        # As duas alternativas puras, sempre, para a comparação ficar explícita.
        so_mercado = resolve_unit_cost(
            item.unique_name, Sourcing.MARKET, precos_compra.get, receita_de,
            return_rate, station_fee,
        )
        so_producao = resolve_unit_cost(
            item.unique_name, Sourcing.CRAFT, precos_compra.get, receita_de,
            return_rate, station_fee,
        )

        venda, idade_venda = precos_venda.get(item.unique_name, (None, None))
        lucro = margem = por_focus = None
        conhecido = cadeia.known and venda is not None and fees.complete
        motivo = cadeia.reason

        if conhecido:
            operacao = compute_trade(1, venda, fees, strategy, quantity=1)
            receita_liquida = operacao.unit_revenue or 0.0
            lucro = receita_liquida - (cadeia.unit_cost or 0.0)
            margem = lucro / venda * 100 if venda else None
            por_focus = (
                lucro / cadeia.focus_per_unit if cadeia.focus_per_unit > 0 else None
            )
        elif venda is None:
            motivo = motivo or "sem cotação de venda"
        elif not fees.complete:
            motivo = "taxas não configuradas: " + ", ".join(fees.missing())

        sinal = next(
            (v for (i, _l, _q), v in sinais.items() if i == item.id and v.known), None
        )

        resultados.append(
            RefiningOut(
                item=item.unique_name,
                item_name=item.display_name_pt or item.display_name_en,
                icon_url=item_icon_url(item.unique_name),
                tier=item.tier,
                enchantment=item.enchantment,
                family=family_of(item.unique_name),
                station_category=(receitas.get(item.id).station_category
                                  if receitas.get(item.id) else None),
                sell_price=venda,
                sell_age_seconds=idade_venda,
                liquidity_units_per_day=sinal.units_per_day if sinal else None,
                sourcing=str(sourcing),
                unit_cost=round(cadeia.unit_cost, 2) if cadeia.known else None,
                focus_per_unit=round(cadeia.focus_per_unit, 2),
                chain=[
                    ChainStepOut(
                        item=passo.unique_name,
                        item_name=(por_nome[passo.unique_name].display_name_pt
                                   or por_nome[passo.unique_name].display_name_en)
                        if passo.unique_name in por_nome else None,
                        icon_url=item_icon_url(passo.unique_name),
                        sourcing=str(passo.sourcing),
                        unit_cost=passo.unit_cost,
                        market_price=passo.market_price,
                        craft_cost=passo.craft_cost,
                        depth=passo.depth,
                    )
                    for passo in _elos_unicos(cadeia.steps)
                ],
                cost_from_market=round(so_mercado.unit_cost, 2) if so_mercado.known else None,
                cost_from_crafting=round(so_producao.unit_cost, 2) if so_producao.known else None,
                known=conhecido,
                reason=None if conhecido else motivo,
                profit=round(lucro, 2) if lucro is not None else None,
                margin_pct=round(margem, 2) if margem is not None else None,
                profit_per_focus=round(por_focus, 2) if por_focus is not None else None,
            )
        )

    resultados.sort(
        key=lambda r: (r.profit_per_focus if r.profit_per_focus is not None else -1e18),
        reverse=True,
    )
    familias = sorted({r.family for r in resultados if r.family})

    return RefiningResponse(
        server=server, buy_location=buy_location, sell_location=sell_location,
        sourcing=str(sourcing), total=len(resultados), params=params,
        generated_at=now.isoformat(), data_source_note=DATA_SOURCE_NOTE,
        families=familias, opportunities=resultados[:limit],
    )


def _elos_unicos(passos):
    """Um elo por item.

    A recursão visita o mesmo tier por caminhos diferentes -- T6 aparece tanto
    como insumo de T7 quanto de T8. Repetir na tela transformaria a cadeia num
    borrão em vez de mostrar onde está o gargalo.
    """
    vistos: set[str] = set()
    unicos = []
    for passo in passos:
        if passo.unique_name in vistos:
            continue
        vistos.add(passo.unique_name)
        unicos.append(passo)
    return sorted(unicos, key=lambda p: p.unique_name)


def _vazio(server, buy_location, sell_location, sourcing, params, familias):
    return RefiningResponse(
        server=server, buy_location=buy_location, sell_location=sell_location,
        sourcing=str(sourcing), total=0, params=params,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE, families=familias, opportunities=[],
    )
