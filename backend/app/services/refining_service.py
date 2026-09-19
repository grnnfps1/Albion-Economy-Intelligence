"""Oportunidades de refino.

Refino é crafting com uma diferença estrutural: a receita consome o recurso
bruto **e o refinado do tier anterior**. Isso transforma a pergunta. Não é "vale
refinar T5?" e sim "onde na cadeia T2→T8 está o gargalo de preço?".

Por isso a tela compara as duas formas de custear o insumo anterior — comprar
pronto ou produzir — em vez de escolher uma por conta própria.

Há uma segunda escolha, independente dessa: *em qual cidade* comprar o que for
comprado. Ela mora em `sourcing.py` e chega aqui como a função de preço que a
cadeia consulta — a recursão continua pura, sem saber que cidades existem.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.chain import ChainResult, RecipeSpec, Sourcing, resolve_unit_cost
from app.calculations.fees import Strategy, compute_trade
from app.calculations.returns import Activity
from app.calculations.station import NUTRITION_PER_ITEM_VALUE
from app.catalog.icons import item_icon_url
from app.core.config import get_settings
from app.models.catalog import Item
from app.models.recipes import Recipe
from app.repositories import market as market_repo
from app.repositories import recipes_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.repositories.reference import list_locations
from app.schemas.crafting import CraftParamsUsed, SourcingOut, SpecializationUsed
from app.schemas.refining import ChainStepOut, RefiningOut, RefiningResponse
from app.services.arbitrage_service import resolve_fees
from app.services.return_service import load_return_policy, return_out
from app.services.sourcing import MaterialSourcing, SourcingMode, load_material_sourcing
from app.services.specialization_service import load_specialization_policy, spec_out
from app.services.station_service import (
    StationFeePolicy,
    item_value_lookup,
    load_station_fee_policy,
)

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
    station_fee_per_100_nutrition: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    family: str | None,
    tier: int | None,
    strategy: Strategy,
    limit: int,
    sourcing_mode: SourcingMode = SourcingMode.SINGLE_CITY,
    max_age_seconds: int | None = None,
    use_focus: bool = False,
    daily_production_bonus: float = 0.0,
    spec_levels: dict[str, int] | None = None,
    spec_item_levels: dict[str, int] | None = None,
) -> RefiningResponse:
    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
    # O bônus de refino segue o recurso, e dentro de uma cadeia o recurso é o
    # mesmo do começo ao fim: madeira bruta e tábua têm a mesma cidade. Por isso
    # basta resolver uma vez por item refinado.
    retornos = await load_return_policy(session)
    nomes_de_cidade = {
        local.slug: local.display_name for local in await list_locations(session)
    }
    if max_age_seconds is None:
        max_age_seconds = get_settings().freshness_stale_seconds

    faltando = list(resumo_taxas.missing)
    matriz = retornos.matrices[Activity.REFINING]
    if return_rate is None and not matriz.complete:
        faltando.append("refining.return_rate")

    # O catálogo ainda não foi carregado; a política ganha o lookup de
    # `item_value` mais abaixo. Aqui só interessa saber se a prata por 100 de
    # nutrição foi informada.
    taxa_estacao = await load_station_fee_policy(
        session, lambda _nome: None, station_fee_per_100_nutrition
    )
    faltando.extend(taxa_estacao.missing())

    # Spec por família de recurso: couro, tecido, tábuas, barras, blocos. Sem
    # nada informado o custo sai igual ao do dump, e a resposta avisa.
    spec = await load_specialization_policy(
        session, spec_levels, item_levels=spec_item_levels
    )

    params = CraftParamsUsed(
        return_rate=return_rate,
        station_fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        nutrition_per_item_value=NUTRITION_PER_ITEM_VALUE,
        use_focus=use_focus, daily_production_bonus=daily_production_bonus,
        return_rate_source="preferencia" if return_rate is not None else "matriz",
        specialization=SpecializationUsed(**spec_out(spec)),
        fees=resumo_taxas, complete=not faltando, missing=faltando,
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
        return _vazio(server, buy_location, sell_location, sourcing, sourcing_mode, params, [])

    # Carrega tudo de uma vez: receitas, preços e liquidez.
    todas = await recipes_repo.list_recipes(session, tracked_only=False, limit=50_000)
    receitas: dict[int, Recipe] = {}
    for receita in todas:
        receitas.setdefault(receita.output_item_id, receita)

    ids = {item.id for item in refinados}
    for receita in receitas.values():
        ids.update(m.item_id for m in receita.materials)
        ids.add(receita.output_item_id)

    catalogo = await recipes_repo.load_items(session, sorted(ids))
    por_nome = {item.unique_name: item for item in catalogo.values()}
    # Cada elo paga a taxa do que ele próprio produz. É aqui que a fase 15 pesa
    # mais: numa cadeia T2→T8 a taxa do topo é 64× a da base, e cobrar a mesma
    # em todos os elos errava a conta nas duas pontas.
    taxa_estacao = StationFeePolicy(
        fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        item_value_of=item_value_lookup(catalogo),
    )
    now = datetime.now(UTC)

    # Venda: só a cidade onde se vende, e só do item refinado.
    linhas, _ = await market_repo.search_prices(
        session, server_code=server, location_slugs=[sell_location], limit=50_000,
    )
    precos_venda: dict[str, tuple[int | None, int | None]] = {}
    for price, item, _location in linhas:
        if strategy is Strategy.FAST:
            precos_venda.setdefault(
                item.unique_name, (price.buy_price_max, _age(price.buy_price_max_date, now))
            )
        else:
            precos_venda.setdefault(
                item.unique_name, (price.sell_price_min, _age(price.sell_price_min_date, now))
            )

    # Compra: a cadeia só alcança os refinados e o que entra neles. Pedir preço
    # do catálogo inteiro para todas as cidades seria varrer o mercado à toa.
    compras = await load_material_sourcing(
        session,
        server_code=server,
        item_unique_names=_nomes_da_cadeia(refinados, receitas, catalogo),
        base_slug=buy_location,
        mode=sourcing_mode,
        max_age_seconds=max_age_seconds,
        now=now,
    )

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
        # A redução entra aqui, no `RecipeSpec`: cada elo da cadeia tem o Focus
        # da sua própria família, e `chain.py` segue sem saber que
        # especialização existe.
        focus = spec.focus_cost_of(unique_name, receita.focus_cost)
        return RecipeSpec(receita.output_quantity, focus.focus, materiais)

    def resolver(nome: str, modo: Sourcing, preco, taxa_retorno) -> ChainResult:
        return resolve_unit_cost(
            nome, modo, preco, receita_de, taxa_retorno, taxa_estacao.silver_of
        )

    resultados: list[RefiningOut] = []
    for item in refinados:
        retorno, melhor_cidade = retornos.resolve(
            Activity.REFINING,
            item.unique_name,
            city_slug=buy_location,
            use_focus=use_focus,
            daily_bonus=daily_production_bonus,
            override=return_rate,
        )
        taxa = retorno.rate

        cadeia = resolver(item.unique_name, sourcing, compras.price_of, taxa)
        # As duas alternativas puras, sempre, para a comparação ficar explícita.
        so_mercado = resolver(item.unique_name, Sourcing.MARKET, compras.price_of, taxa)
        so_producao = resolver(item.unique_name, Sourcing.CRAFT, compras.price_of, taxa)

        venda, idade_venda = precos_venda.get(item.unique_name, (None, None))
        lucro = margem = por_focus = None
        conhecido = cadeia.known and venda is not None and fees.complete
        motivo = cadeia.reason

        if conhecido:
            lucro, margem, por_focus = _resultado(cadeia, venda, fees, strategy)
        elif venda is None:
            motivo = motivo or "sem cotação de venda"
        elif not fees.complete:
            motivo = "taxas não configuradas: " + ", ".join(fees.missing())

        elos = _elos_unicos(cadeia.steps)
        roteiro = _roteiro(
            sourcing_mode, elos, compras, cadeia,
            lambda nome=item.unique_name, t=taxa: resolver(
                nome, sourcing, compras.base_price_of, t
            ),
            venda, fees, strategy,
        )

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
                chain=[_elo_out(passo, por_nome, compras) for passo in elos],
                material_sourcing=roteiro,
                material_return=return_out(retorno, melhor_cidade, nomes_de_cidade),
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
        sourcing=str(sourcing), sourcing_mode=str(sourcing_mode),
        total=len(resultados), params=params,
        generated_at=now.isoformat(), data_source_note=DATA_SOURCE_NOTE,
        families=familias, opportunities=resultados[:limit],
    )


def _resultado(cadeia: ChainResult, venda: int, fees, strategy: Strategy):
    """Lucro, margem e prata/focus de uma unidade refinada."""
    operacao = compute_trade(1, venda, fees, strategy, quantity=1)
    receita_liquida = operacao.unit_revenue or 0.0
    lucro = receita_liquida - (cadeia.unit_cost or 0.0)
    margem = lucro / venda * 100 if venda else None
    por_focus = lucro / cadeia.focus_per_unit if cadeia.focus_per_unit > 0 else None
    return lucro, margem, por_focus


def _nomes_da_cadeia(refinados, receitas, catalogo) -> list[str]:
    """Os itens que a cadeia pode alcançar a partir dos refinados listados.

    Percorre o grafo de receitas em vez de pedir preço para o catálogo inteiro:
    são 12 mil itens, e a cadeia de refino toca algumas centenas. O conjunto de
    visitados também corta ciclo, pelo mesmo motivo que `chain.py` corta.
    """
    fila = [item.id for item in refinados]
    vistos: set[int] = set()
    while fila:
        item_id = fila.pop()
        if item_id in vistos:
            continue
        vistos.add(item_id)
        receita = receitas.get(item_id)
        if receita is None:
            continue
        fila.extend(m.item_id for m in receita.materials if m.item_id not in vistos)
    return sorted({catalogo[i].unique_name for i in vistos if i in catalogo})


def _elo_out(passo, por_nome, compras: MaterialSourcing) -> ChainStepOut:
    item = por_nome.get(passo.unique_name)
    comprado = passo.sourcing is Sourcing.MARKET
    escolha = compras.choose(passo.unique_name)
    cotacao = escolha.quote if escolha.known else None

    return ChainStepOut(
        item=passo.unique_name,
        item_name=(item.display_name_pt or item.display_name_en) if item else None,
        icon_url=item_icon_url(passo.unique_name),
        sourcing=str(passo.sourcing),
        unit_cost=passo.unit_cost,
        market_price=passo.market_price,
        craft_cost=passo.craft_cost,
        depth=passo.depth,
        # Cidade só faz sentido no elo que é de fato comprado. Marcar a cidade
        # de um elo produzido sugeriria uma compra que não acontece.
        location=cotacao.location_name if (comprado and cotacao) else None,
        location_slug=cotacao.location_slug if (comprado and cotacao) else None,
        is_alternate_city=escolha.is_alternate if comprado else False,
        base_unit_price=(
            escolha.base.unit_price if comprado and escolha.base is not None else None
        ),
        savings_vs_base=(
            round(escolha.savings_per_unit, 2)
            if comprado and escolha.savings_per_unit is not None
            else None
        ),
    )


def _roteiro(
    mode: SourcingMode,
    elos,
    compras: MaterialSourcing,
    cadeia: ChainResult,
    resolver_base,
    venda: int | None,
    fees,
    strategy: Strategy,
) -> SourcingOut:
    """Em quantas cidades a cadeia cai, e quanto o espalhamento rende.

    Conta só os elos efetivamente comprados: um elo produzido não exige viagem
    nenhuma.
    """
    cidades = sorted(
        {
            quote.location_name
            for passo in elos
            if passo.sourcing is Sourcing.MARKET
            for quote in [compras.choose(passo.unique_name).quote]
            if quote is not None and quote.usable
        }
    )

    if mode is SourcingMode.SINGLE_CITY:
        return SourcingOut(
            mode=str(mode),
            cities_involved=len(cidades),
            cities=cidades,
            cost_single_city=round(cadeia.unit_cost, 2) if cadeia.known else None,
        )

    base = resolver_base()
    custo_unica = round(base.unit_cost, 2) if base.known else None
    custo_barato = round(cadeia.unit_cost, 2) if cadeia.known else None
    economia = (
        None
        if custo_unica is None or custo_barato is None
        else round(custo_unica - custo_barato, 2)
    )

    lucro_unica = lucro_barato = None
    if mode is SourcingMode.COMPARE and venda is not None and fees.complete:
        if base.known:
            lucro_unica = round(_resultado(base, venda, fees, strategy)[0], 2)
        if cadeia.known:
            lucro_barato = round(_resultado(cadeia, venda, fees, strategy)[0], 2)

    return SourcingOut(
        mode=str(mode),
        cities_involved=len(cidades),
        cities=cidades,
        cost_single_city=custo_unica,
        cost_cheapest=custo_barato,
        savings=economia,
        savings_pct=(
            round(economia / custo_unica * 100, 2)
            if economia is not None and custo_unica
            else None
        ),
        profit_single_city=lucro_unica,
        profit_cheapest=lucro_barato,
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


def _vazio(server, buy_location, sell_location, sourcing, sourcing_mode, params, familias):
    return RefiningResponse(
        server=server, buy_location=buy_location, sell_location=sell_location,
        sourcing=str(sourcing), sourcing_mode=str(sourcing_mode), total=0, params=params,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE, families=familias, opportunities=[],
    )
