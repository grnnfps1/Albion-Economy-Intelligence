"""Oportunidades de crafting.

Junta três coisas que vivem separadas: a receita (dump do jogo), o preço dos
materiais (mercado da cidade onde se compra) e o preço de venda do item final
(mercado da cidade onde se vende).

O cálculo em si é puro e mora em `calculations/crafting.py`. Aqui fica a
política: onde comprar, onde vender, o que descartar antes de calcular. Em qual
cidade comprar cada material é política também, e mora em `sourcing.py`.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.crafting import CraftEconomics, MaterialCost, compute_craft
from app.calculations.daily import daily_yield
from app.calculations.fees import FeeProfile, Strategy
from app.calculations.returns import Activity
from app.calculations.risk import adjust_for_risk
from app.calculations.specialization import FocusCost
from app.calculations.station import NUTRITION_PER_ITEM_VALUE, StationFee
from app.catalog.icons import item_icon_url
from app.core.config import get_settings
from app.models.market import MarketPrice
from app.repositories import market as market_repo
from app.repositories import recipes_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.repositories.reference import list_locations
from app.schemas.crafting import (
    CraftEconomicsOut,
    CraftingResponse,
    CraftOpportunityOut,
    CraftParamsUsed,
    MaterialOut,
    SourcingOut,
    SpecializationUsed,
)
from app.services.arbitrage_service import resolve_fees
from app.services.return_service import load_return_policy, return_out
from app.services.risk_service import load_route_zones, resolve_risk, risk_out
from app.services.sourcing import MaterialSourcing, SourcingMode, load_material_sourcing
from app.services.specialization_service import load_specialization_policy, spec_out
from app.services.station_service import (
    StationFeePolicy,
    item_value_lookup,
    load_station_fee_policy,
)

DATA_SOURCE_NOTE = (
    "Custos e receita vêm da coleta comunitária do AODP; as receitas vêm do dump "
    "oficial do jogo. Um material sem cotação torna o craft inteiro desconhecido: "
    "custo parcial não é custo menor."
)

RETURN_RATE_KEY = "crafting.return_rate.base"


def _age(value: datetime | None, now: datetime) -> int | None:
    return None if value is None else max(0, int((now - value).total_seconds()))


async def find_crafting_opportunities(
    session: AsyncSession,
    server: str,
    buy_location: str,
    sell_location: str,
    return_rate: float | None,
    station_fee_per_100_nutrition: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    crafts: int,
    strategy: Strategy,
    sort_by: str,
    tier: int | None,
    station_category: str | None,
    limit: int,
    sourcing_mode: SourcingMode = SourcingMode.SINGLE_CITY,
    max_age_seconds: int | None = None,
    loss_pct_blue: float | None = None,
    loss_pct_red_black: float | None = None,
    use_focus: bool = False,
    daily_production_bonus: float = 0.0,
    spec_levels: dict[str, int] | None = None,
    spec_item_levels: dict[str, int] | None = None,
    focus_per_day: float | None = None,
) -> CraftingResponse:
    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
    perfil_risco, resumo_risco = await resolve_risk(session, loss_pct_blue, loss_pct_red_black)
    # A rota do craft é uma só para a resposta inteira: compra numa cidade,
    # vende em outra. Basta classificar uma vez.
    zonas = await load_route_zones(session)
    zona = zonas.of(buy_location, sell_location)

    # O retorno é resolvido por item: depende da cidade onde se crafta e de o
    # Focus estar ligado. `return_rate` deixou de ser o valor primário e virou
    # sobrescrita opcional — o contrário da precedência das taxas de mercado.
    retornos = await load_return_policy(session)
    nomes_de_cidade = {
        local.slug: local.display_name for local in await list_locations(session)
    }

    if max_age_seconds is None:
        # Acima do limite de frescor o preço deixa de justificar um desvio de
        # cidade: a ordem que o barateava provavelmente já foi consumida.
        max_age_seconds = get_settings().freshness_stale_seconds

    faltando = list(resumo_taxas.missing)
    # A taxa agora é derivada dos bônus; o que pode faltar são os
    # componentes, não uma célula.
    if return_rate is None and not retornos.components.complete:
        faltando.append("crafting.return_rate")

    # A taxa da estação precisa do catálogo para saber o `item_value` de cada
    # item, e o catálogo só é carregado depois das receitas. Até lá a política
    # existe sem lookup: serve para saber se a prata por 100 de nutrição foi
    # informada, que é a parte que pode faltar.
    taxa_estacao = await load_station_fee_policy(
        session, lambda _nome: None, station_fee_per_100_nutrition
    )
    faltando.extend(taxa_estacao.missing())

    # Spec ausente é zero, não UNKNOWN: o custo sai igual ao do dump e a
    # resposta diz que assumiu zero. É a regra do risco de rota, não a das
    # taxas.
    spec = await load_specialization_policy(
        session, spec_levels, item_levels=spec_item_levels
    )

    params = CraftParamsUsed(
        return_rate=return_rate,
        station_fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        nutrition_per_item_value=NUTRITION_PER_ITEM_VALUE,
        use_focus=use_focus,
        daily_production_bonus=daily_production_bonus,
        return_rate_source="preferencia" if return_rate is not None else "formula",
        specialization=SpecializationUsed(**spec_out(spec)),
        fees=resumo_taxas,
        complete=not faltando,
        missing=faltando,
    )

    receitas = await recipes_repo.list_recipes(
        session, station_category=station_category, tier=tier, tracked_only=True, limit=limit * 6
    )
    if not receitas:
        return _empty(
            server, buy_location, sell_location, crafts, sort_by, sourcing_mode,
            params, resumo_risco,
        )

    ids = {r.output_item_id for r in receitas}
    for receita in receitas:
        ids.update(m.item_id for m in receita.materials)

    catalogo = await recipes_repo.load_items(session, sorted(ids))
    # Agora o `item_value` está disponível: a política ganha o lookup de verdade.
    taxa_estacao = StationFeePolicy(
        fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        item_value_of=item_value_lookup(catalogo),
    )
    now = datetime.now(UTC)

    # Preço do item final: só interessa na cidade onde se vende.
    linhas, _ = await market_repo.search_prices(
        session, server_code=server, location_slugs=[sell_location], limit=20_000
    )
    precos_venda: dict[int, MarketPrice] = {}
    for price, item, _location in linhas:
        # Qualidade 1 e 2 são as que interessam para craft normal; fica com a
        # primeira encontrada para não misturar qualidades.
        precos_venda.setdefault(item.id, price)

    # Onde comprar cada material. Em CIDADE_UNICA a consulta se restringe à
    # cidade base; nos outros modos ela varre as cidades ativas.
    nomes_materiais = sorted(
        {
            catalogo[m.item_id].unique_name
            for receita in receitas
            for m in receita.materials
            if m.item_id in catalogo
        }
    )
    compras = await load_material_sourcing(
        session,
        server_code=server,
        item_unique_names=nomes_materiais,
        base_slug=buy_location,
        mode=sourcing_mode,
        max_age_seconds=max_age_seconds,
        now=now,
    )

    sinais = await liquidity_by_item_location(session, server, sorted(ids))
    resultados: list[CraftOpportunityOut] = []

    for receita in receitas:
        saida = catalogo.get(receita.output_item_id)
        if saida is None:
            continue

        preco_venda = precos_venda.get(saida.id)
        sell_price = None
        sell_age = None
        if preco_venda is not None:
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

        # O bônus de craft segue a família do item e vale na cidade onde se
        # produz — aqui, a mesma em que se compra material.
        retorno, melhor_cidade = retornos.resolve(
            Activity.CRAFTING,
            saida.unique_name,
            city_slug=buy_location,
            use_focus=use_focus,
            daily_bonus=daily_production_bonus,
            override=return_rate,
        )

        contexto = _Contexto(
            sell_price=sell_price,
            fees=fees,
            return_rate=retorno.rate,
            # A taxa é do item que está sendo produzido, não um valor único da
            # resposta: ela dobra a cada tier junto com o `item_value`.
            station_fee=taxa_estacao.fee_of(saida.unique_name),
            focus_cost=spec.focus_cost_of(saida.unique_name, receita.focus_cost),
            crafts=crafts,
            strategy=strategy,
        )

        materiais, materiais_out, cidades = _materiais_da_rota(receita, catalogo, compras)
        economia = contexto.calcular(receita, materiais)
        roteiro = _roteiro(sourcing_mode, cidades, economia, receita, catalogo, compras, contexto)

        # O capital em risco é o que sai do bolso antes de vender: material pelo
        # preço cheio (o retorno só se realiza depois) mais a taxa da estação.
        investimento = (
            None
            if economia.material_cost_gross is None
            else economia.material_cost_gross + (economia.station_fee or 0.0)
        )
        risco = adjust_for_risk(economia.profit, investimento, zona, perfil_risco)

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
                material_sourcing=roteiro,
                risk=risk_out(risco),
                material_return=return_out(retorno, melhor_cidade, nomes_de_cidade),
                economics=CraftEconomicsOut(
                    **_por_dia(economia, sinal, focus_per_day),
                    known=economia.known,
                    reason=economia.reason,
                    output_quantity=economia.output_quantity,
                    focus_cost=economia.focus_cost,
                    base_focus_cost=economia.base_focus_cost,
                    focus_multiplier=economia.focus_multiplier,
                    material_cost_gross=economia.material_cost_gross,
                    material_cost_net=economia.material_cost_net,
                    returned_value=economia.returned_value,
                    station_fee=economia.station_fee,
                    item_value=economia.item_value,
                    nutrition=economia.nutrition,
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
        # Ordena pelo lucro **ajustado ao risco**. Com risco em zero os dois são
        # iguais; quando não são, ranquear pelo bruto colocaria a rota que
        # atravessa zona aberta no topo justamente por ela pagar o prêmio.
        lucro = (
            op.risk.expected_profit
            if op.risk.expected_profit is not None
            else (op.economics.profit or 0.0)
        )
        if sort_by == "profit":
            return lucro
        if sort_by == "roi":
            return op.economics.roi_pct or 0.0
        focus = op.economics.focus_cost
        return lucro / focus if focus > 0 else -1

    resultados.sort(key=chave, reverse=True)

    return CraftingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        crafts=crafts,
        sort_by=sort_by,
        sourcing_mode=str(sourcing_mode),
        total=len(resultados),
        params=params,
        risk=resumo_risco,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        opportunities=resultados[:limit],
    )


class _Contexto:
    """Tudo que não muda entre os dois roteiros de compra da mesma receita.

    Existe para que o roteiro de comparação seja o mesmo cálculo com outro
    conjunto de preços -- e não uma segunda fórmula que pode divergir da
    primeira.
    """

    def __init__(
        self,
        sell_price: int | None,
        fees: FeeProfile,
        return_rate: float | None,
        station_fee: StationFee,
        focus_cost: FocusCost,
        crafts: int,
        strategy: Strategy,
    ) -> None:
        self.sell_price = sell_price
        self.fees = fees
        self.return_rate = return_rate
        self.station_fee = station_fee
        self.focus_cost = focus_cost
        self.crafts = crafts
        self.strategy = strategy

    def calcular(self, receita, materiais: list[MaterialCost]) -> CraftEconomics:
        return compute_craft(
            materials=materiais,
            sell_price=self.sell_price,
            fees=self.fees,
            return_rate=self.return_rate,
            station_fee=self.station_fee,
            output_quantity=receita.output_quantity,
            focus_cost=self.focus_cost,
            crafts=self.crafts,
            strategy=self.strategy,
        )


def _materiais_da_rota(
    receita, catalogo, compras: MaterialSourcing
) -> tuple[list[MaterialCost], list[MaterialOut], list[str]]:
    """Materiais com a cidade que a política escolheu para cada um."""
    custos: list[MaterialCost] = []
    saida: list[MaterialOut] = []
    cidades: list[str] = []

    for material in receita.materials:
        item = catalogo.get(material.item_id)
        if item is None:
            continue

        escolha = compras.choose(item.unique_name)
        cotacao = escolha.quote if escolha.known else None
        unit = escolha.unit_price
        nome_cidade = cotacao.location_name if cotacao else None
        idade = cotacao.age_seconds if cotacao else None
        if nome_cidade is not None:
            cidades.append(nome_cidade)

        economia_linha = (
            None
            if escolha.savings_per_unit is None
            else round(escolha.savings_per_unit * material.quantity, 2)
        )
        base = escolha.base

        custos.append(
            MaterialCost(
                unique_name=item.unique_name,
                display_name=item.display_name_pt or item.display_name_en,
                quantity=material.quantity,
                unit_price=unit,
                is_returnable=material.is_returnable,
                location=nome_cidade,
                age_seconds=idade,
            )
        )
        saida.append(
            MaterialOut(
                item=item.unique_name,
                item_name=item.display_name_pt or item.display_name_en,
                icon_url=item_icon_url(item.unique_name),
                quantity=material.quantity,
                unit_price=unit,
                total_price=None if unit is None else unit * material.quantity,
                is_returnable=material.is_returnable,
                location=nome_cidade,
                location_slug=cotacao.location_slug if cotacao else None,
                age_seconds=idade,
                is_alternate_city=escolha.is_alternate,
                base_unit_price=base.unit_price if base is not None else None,
                savings_vs_base=economia_linha,
            )
        )

    return custos, saida, cidades


def _materiais_da_cidade_base(receita, catalogo, compras: MaterialSourcing) -> list[MaterialCost]:
    """O mesmo craft comprando tudo na cidade base -- o roteiro de comparação."""
    return [
        MaterialCost(
            unique_name=catalogo[m.item_id].unique_name,
            display_name=None,
            quantity=m.quantity,
            unit_price=compras.base_price_of(catalogo[m.item_id].unique_name),
            is_returnable=m.is_returnable,
        )
        for m in receita.materials
        if m.item_id in catalogo
    ]


def _roteiro(
    mode: SourcingMode,
    cidades: list[str],
    economia: CraftEconomics,
    receita,
    catalogo,
    compras: MaterialSourcing,
    contexto: _Contexto,
) -> SourcingOut:
    """Em quantas cidades a rota cai, e quanto o espalhamento rende.

    Economia sem o número de cidades engana: 3% espalhados por quatro cidades
    custam quatro viagens e não são economia nenhuma. Por isso os dois números
    saem juntos.
    """
    distintas = sorted(set(cidades))

    if mode is SourcingMode.SINGLE_CITY:
        return SourcingOut(
            mode=str(mode),
            cities_involved=len(distintas),
            cities=distintas,
            cost_single_city=economia.material_cost_net,
        )

    base = contexto.calcular(receita, _materiais_da_cidade_base(receita, catalogo, compras))
    custo_unica = base.material_cost_net
    custo_barato = economia.material_cost_net
    # Custo desconhecido de um lado não vira economia do outro: quando a cidade
    # base não consegue custear a receita, não há comparação a fazer.
    economia_total = (
        None
        if custo_unica is None or custo_barato is None
        else round(custo_unica - custo_barato, 2)
    )

    return SourcingOut(
        mode=str(mode),
        cities_involved=len(distintas),
        cities=distintas,
        cost_single_city=custo_unica,
        cost_cheapest=custo_barato,
        savings=economia_total,
        savings_pct=(
            round(economia_total / custo_unica * 100, 2)
            if economia_total is not None and custo_unica
            else None
        ),
        # COMPARAR leva os dois roteiros até o lucro, não só até o custo.
        profit_single_city=base.profit if mode is SourcingMode.COMPARE else None,
        profit_cheapest=economia.profit if mode is SourcingMode.COMPARE else None,
    )


def _por_dia(economia, sinal, focus_per_day: float | None) -> dict:
    """O bloco de lucro por dia, pronto para o schema.

    O Focus por unidade é o total da execução dividido pelas unidades: é ele
    que se compara com o Focus que regenera num dia.
    """
    unidades = max(1, economia.output_quantity)
    lucro_unitario = None if economia.profit is None else economia.profit / unidades
    focus_unitario = economia.focus_cost / unidades if economia.focus_cost else 0.0

    dia = daily_yield(
        unit_profit=lucro_unitario,
        focus_per_unit=focus_unitario,
        focus_per_day=focus_per_day,
        market_units_per_day=sinal.units_per_day if sinal and sinal.known else None,
    )
    return {
        "profit_per_day": dia.profit,
        "units_per_day": dia.units,
        "daily_limiter": str(dia.limiter),
        "daily_reason": dia.reason,
    }


def _empty(
    server, buy_location, sell_location, crafts, sort_by, sourcing_mode, params, risco
) -> CraftingResponse:
    return CraftingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        crafts=crafts,
        sort_by=sort_by,
        sourcing_mode=str(sourcing_mode),
        total=0,
        params=params,
        risk=risco,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        opportunities=[],
    )
