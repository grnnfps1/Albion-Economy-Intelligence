"""Planos de agricultura e criação.

Três perguntas diferentes moram na mesma tela, porque respondem à mesma decisão
— o que colocar na parcela hoje:

- **cultivo**: semente → colheita, 22 horas;
- **criação**: filhote → adulto, consumindo cultivo como ração;
- **produto**: adulto → leite ou ovo, sem consumir o adulto.

O que as torna comparáveis é a normalização por dia. Um ciclo de fazenda leva
22 horas e um filhote de montaria T8 leva 28 dias: ordenar por "lucro por ciclo"
colocaria a montaria em primeiro por ser lenta, o que é o contrário da verdade.

A criação é cadeia — a ração sai da fazenda — e é por isso que ela reaproveita
a mesma política de compra do refino: onde comprar cada insumo é decisão do
serviço, e o cálculo só recebe preço.

**O que foi lido e o que foi interpretado vão separados na resposta.** O dump
diz o tempo, o custo em Focus por ciclo e o consumo de nutrição. Ele não diz
quantos ciclos de Focus uma criação aceita, nem o que `@activefarmbonus`
multiplica. Isso vira `params.assumptions`, e a lista de verificação está em
`docs/04-taxas.md`.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.farming import (
    FarmEconomics,
    FarmInput,
    FarmOutput,
    PlanKind,
    compute_farm_cycle,
)
from app.calculations.fees import Strategy
from app.catalog.icons import item_icon_url
from app.core.config import get_settings
from app.models.catalog import Item
from app.models.farming import Farmable
from app.models.market import MarketPrice
from app.repositories import farming_repo, recipes_repo
from app.repositories import market as market_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.schemas.crafting import SourcingOut
from app.schemas.farming import (
    FarmEconomicsOut,
    FarmingParamsUsed,
    FarmingResponse,
    FarmInputOut,
    FarmOutputOut,
    FarmPlanOut,
)
from app.services.arbitrage_service import resolve_fees
from app.services.sourcing import Choice, MaterialSourcing, SourcingMode, load_material_sourcing

DATA_SOURCE_NOTE = (
    "Tempo, custo em Focus e consumo de ração vêm do dump oficial; preço vem da "
    "coleta comunitária do AODP. Tudo aparece normalizado por dia: 22 horas de "
    "fazenda e 28 dias de criação não se comparam por ciclo."
)

STATION_LABELS = {
    "farm": "fazenda",
    "herbgarden": "horta",
    "pasture": "pasto",
    "kennel": "canil",
}

# O que foi interpretado, e não lido literalmente. Vai na resposta porque um
# número plausível ao lado de um número medido, sem etiqueta, vira medido.
ASSUMPTIONS = [
    "Focus de uma criação = @activefarmfocuscost × @activefarmmaxcycles. "
    "A leitura não foi verificada no jogo (docs/04-taxas.md).",
    "@activefarmbonus está gravado no banco mas não entra no cálculo: o que ele "
    "multiplica não foi verificado.",
    "A colheita é faixa no dump (3-6 por pé); o cálculo usa a média da faixa.",
    "Ração = grow_seconds ÷ @secondspernutrition pontos de nutrição, convertidos "
    "pelo @nutrition do alimento mais barato da categoria aceita.",
    "O adulto que dá leite ou ovo não é consumido, então o ROI do plano PRODUTO "
    "ignora o capital parado nele.",
    "O bônus de comida favorita (@favoritebonus) não é aplicado: o efeito não foi medido.",
    "O custo usa o preço de mercado da semente ou do filhote. O comerciante de "
    "fazenda vende por prata fixa (npc_silver_cost na resposta) e pode sair mais "
    "barato — a comparação fica explícita em vez de o motor escolher por você.",
]

ORDENACOES = ("profit_per_day", "profit_per_focus", "profit_per_cycle")


def _age(value: datetime | None, now: datetime) -> int | None:
    return None if value is None else max(0, int((now - value).total_seconds()))


async def find_farming_plans(
    session: AsyncSession,
    server: str,
    buy_location: str,
    sell_location: str,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    station: str | None,
    kind: str | None,
    tier: int | None,
    strategy: Strategy,
    sort_by: str,
    limit: int,
    sort_desc: bool = True,
    sourcing_mode: SourcingMode = SourcingMode.SINGLE_CITY,
    max_age_seconds: int | None = None,
) -> FarmingResponse:
    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
    if max_age_seconds is None:
        max_age_seconds = get_settings().freshness_stale_seconds

    params = FarmingParamsUsed(
        fees=resumo_taxas,
        complete=resumo_taxas.complete,
        missing=list(resumo_taxas.missing),
        assumptions=ASSUMPTIONS,
    )

    farmables = await farming_repo.list_farmables(session, station=station, tier=tier, limit=1000)
    if not farmables:
        return _vazio(server, buy_location, sell_location, sort_by, sourcing_mode, params)

    now = datetime.now(UTC)

    # Catálogo de tudo que aparece: o próprio farmable, o adulto e cada saída.
    ids = {f.item_id for f in farmables}
    ids.update(f.grown_item_id for f in farmables if f.grown_item_id)
    for farmable in farmables:
        ids.update(o.item_id for o in farmable.outputs)

    racoes = await farming_repo.food_items(
        session, sorted({f.accepted_food_category for f in farmables if f.accepted_food_category})
    )
    ids.update(item.id for item in racoes)

    catalogo = await recipes_repo.load_items(session, sorted(ids))

    # Compra: semente, filhote e ração. Venda: colheita, adulto, leite e ovo.
    nomes_compra = sorted(
        {catalogo[f.item_id].unique_name for f in farmables if f.item_id in catalogo}
        | {item.unique_name for item in racoes}
    )
    compras = await load_material_sourcing(
        session,
        server_code=server,
        item_unique_names=nomes_compra,
        base_slug=buy_location,
        mode=sourcing_mode,
        max_age_seconds=max_age_seconds,
        now=now,
    )

    linhas, _ = await market_repo.search_prices(
        session, server_code=server, location_slugs=[sell_location], limit=20_000
    )
    precos_venda: dict[int, MarketPrice] = {}
    for price, item, _location in linhas:
        precos_venda.setdefault(item.id, price)

    def preco_de_venda(item_id: int) -> int | None:
        price = precos_venda.get(item_id)
        if price is None:
            return None
        return price.buy_price_max if strategy is Strategy.FAST else price.sell_price_min

    racao = _melhor_racao(racoes, compras)
    sinais = await liquidity_by_item_location(session, server, sorted(ids))

    planos: list[FarmPlanOut] = []
    for farmable in farmables:
        item = catalogo.get(farmable.item_id)
        if item is None:
            continue
        plano = _montar(
            farmable, item, catalogo, compras, racao, preco_de_venda, fees, strategy, sinais,
            buy_location, sell_location,
        )
        if plano is not None and (kind is None or plano.kind == kind):
            planos.append(plano)

    ordem = sort_by if sort_by in ORDENACOES else "profit_per_day"

    def chave(plano: FarmPlanOut) -> float:
        if not plano.economics.known:
            return float("-inf")
        valor = getattr(plano.economics, ordem)
        return valor if valor is not None else float("-inf")

    def posicao(plano: FarmPlanOut):
        """Desconhecido no fim, nas duas direções — mesma regra das outras telas.

        Nome diferente de `ordem` de propósito: `ordem` é a **chave** escolhida
        (`profit_per_day`, …), e uma função com o mesmo nome a sombreava —
        `getattr(economics, ordem)` passava a receber a função.

        A separação entra antes do valor na tupla e o sinal entra no valor; com
        `reverse`, a inversão pegaria também a separação.
        """
        return (not plano.economics.known, -chave(plano) if sort_desc else chave(plano))

    planos.sort(key=posicao)

    return FarmingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        sort_by=ordem,
        sort_dir="desc" if sort_desc else "asc",
        sourcing_mode=str(sourcing_mode),
        total=len(planos),
        params=params,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        stations=sorted({p.station for p in planos}),
        plans=planos[:limit],
    )


# --------------------------------------------------------------------------- #
# Ração
# --------------------------------------------------------------------------- #


def _melhor_racao(racoes: list[Item], compras: MaterialSourcing) -> dict[str, tuple[Item, Choice]]:
    """Alimento mais barato **por ponto de nutrição**, por categoria.

    O mais barato por unidade não é o mais barato por nutrição: uma cenoura T1 e
    um trigo T3 alimentam o mesmo tanto (48 pontos cada), mas um adulto vale
    milhares. Comparar por unidade escolheria errado com frequência.
    """
    melhor: dict[str, tuple[Item, Choice]] = {}
    for item in racoes:
        if not item.food_category or not item.nutrition:
            continue
        escolha = compras.choose(item.unique_name)
        if not escolha.known:
            continue
        por_nutricao = escolha.unit_price / item.nutrition
        atual = melhor.get(item.food_category)
        if atual is None or por_nutricao < atual[1].unit_price / (atual[0].nutrition or 1):
            melhor[item.food_category] = (item, escolha)
    return melhor


def _nutricao_total(farmable: Farmable, segundos: int) -> float | None:
    """Pontos de nutrição que o bicho consome no período.

    Um ponto a cada `@secondspernutrition` segundos. Sem o campo, o consumo é
    desconhecido -- e desconhecido não vira zero.
    """
    if farmable.seconds_per_nutrition is None or float(farmable.seconds_per_nutrition) <= 0:
        return None
    return segundos / float(farmable.seconds_per_nutrition)


# --------------------------------------------------------------------------- #
# Montagem do plano
# --------------------------------------------------------------------------- #


def _entrada_out(
    item: Item, papel: str, quantidade: float, escolha: Choice
) -> FarmInputOut:
    cotacao = escolha.quote if escolha.known else None
    return FarmInputOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name),
        role=papel,
        quantity=round(quantidade, 4),
        unit_price=escolha.unit_price,
        total_price=(
            None
            if escolha.unit_price is None
            else round(escolha.unit_price * quantidade, 2)
        ),
        location=cotacao.location_name if cotacao else None,
        location_slug=cotacao.location_slug if cotacao else None,
        age_seconds=cotacao.age_seconds if cotacao else None,
        is_alternate_city=escolha.is_alternate,
        savings_vs_base=(
            None
            if escolha.savings_per_unit is None
            else round(escolha.savings_per_unit * quantidade, 2)
        ),
    )


def _saida_out(item: Item, saida: FarmOutput, papel: str) -> FarmOutputOut:
    return FarmOutputOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name),
        role=papel,
        amount_min=saida.amount_min,
        amount_max=saida.amount_max,
        chance=round(saida.chance, 4),
        expected_amount=round(saida.expected_amount, 4),
        unit_price=saida.unit_price,
        primary=saida.primary,
    )


def _montar(
    farmable: Farmable,
    item: Item,
    catalogo: dict[int, Item],
    compras: MaterialSourcing,
    racao: dict[str, tuple[Item, Choice]],
    preco_de_venda,
    fees,
    strategy: Strategy,
    sinais,
    buy_location: str,
    sell_location: str,
) -> FarmPlanOut | None:
    """Um farmable vira um plano — ou nenhum, quando ele não fecha um ciclo."""
    if farmable.role == "seed":
        tipo = PlanKind.CROP
        ciclo = farmable.grow_seconds or farmable.cycle_seconds or 0
    elif farmable.role == "baby":
        tipo = PlanKind.BREEDING
        ciclo = farmable.grow_seconds or 0
    elif farmable.product_seconds:
        tipo = PlanKind.PRODUCT
        ciclo = farmable.product_seconds
    else:
        # Adulto que não produz nada é saída de uma criação, não plano próprio.
        # Uma linha para ele seria uma decisão que ninguém toma.
        return None

    entradas: list[FarmInput] = []
    entradas_out: list[FarmInputOut] = []
    cidades: list[str] = []

    def registrar(item_insumo: Item, papel: str, quantidade: float) -> None:
        escolha = compras.choose(item_insumo.unique_name)
        entradas.append(
            FarmInput(
                unique_name=item_insumo.unique_name,
                display_name=item_insumo.display_name_pt or item_insumo.display_name_en,
                quantity=quantidade,
                unit_price=escolha.unit_price,
                location=escolha.quote.location_name if escolha.known else None,
                age_seconds=escolha.quote.age_seconds if escolha.known else None,
            )
        )
        entradas_out.append(_entrada_out(item_insumo, papel, quantidade, escolha))
        if escolha.known:
            cidades.append(escolha.quote.location_name)

    if tipo is not PlanKind.PRODUCT:
        registrar(item, "semente" if tipo is PlanKind.CROP else "filhote", 1.0)

    # Ração: só quem tem consumo declarado come.
    if farmable.accepted_food_category:
        escolhida = racao.get(farmable.accepted_food_category)
        nutricao = _nutricao_total(farmable, ciclo)
        if escolhida is None or nutricao is None:
            return _plano_desconhecido(
                farmable,
                item,
                tipo,
                ciclo,
                entradas_out,
                cidades,
                compras,
                buy_location,
                sell_location,
                f"sem ração com cotação na categoria {farmable.accepted_food_category}"
                if escolhida is None
                else "o dump não diz o consumo de nutrição deste animal",
            )
        alimento, _escolha = escolhida
        registrar(alimento, "ração", nutricao / alimento.nutrition)

    saidas: list[FarmOutput] = []
    saidas_out: list[FarmOutputOut] = []
    principais = _principais(farmable)
    principal_id: int | None = None

    for saida in farmable.outputs:
        alvo = catalogo.get(saida.item_id)
        if alvo is None:
            continue
        principal = saida.id in principais
        if principal and principal_id is None:
            principal_id = alvo.id

        if saida.role == "seed_return":
            # A semente que volta é replantada, não vendida: vale o que custaria
            # comprá-la de novo e não paga imposto de venda.
            preco = compras.choose(alvo.unique_name).unit_price
            taxada = False
        else:
            preco = preco_de_venda(alvo.id)
            taxada = True

        modelo = FarmOutput(
            unique_name=alvo.unique_name,
            display_name=alvo.display_name_pt or alvo.display_name_en,
            amount_min=saida.amount_min,
            amount_max=saida.amount_max,
            chance=float(saida.chance),
            unit_price=preco,
            primary=principal,
            taxed=taxada,
        )
        saidas.append(modelo)
        saidas_out.append(_saida_out(alvo, modelo, saida.role))

    economia = compute_farm_cycle(
        kind=tipo,
        inputs=entradas,
        outputs=saidas,
        fees=fees,
        cycle_seconds=ciclo,
        focus_cost=_focus_total(farmable, tipo),
        strategy=strategy,
    )

    sinal = next(
        (v for (i, _l, _q), v in sinais.items() if i == principal_id and v.known), None
    )

    return _plano(
        farmable, item, tipo, entradas_out, saidas_out, cidades, compras,
        buy_location, sell_location, economia, sinal.units_per_day if sinal else None,
    )


def _principais(farmable: Farmable) -> set[int]:
    """Quais saídas o ciclo existe para produzir.

    Não é "tudo que vem na lista de loot": `T1_CARROT_LOOT` traz a cenoura com
    chance 1.0 **e** uma minhoca com chance 0.1. A minhoca cai junto, não é o
    motivo de plantar cenoura -- e tratá-la como principal faria um cultivo
    inteiro virar UNKNOWN só porque ninguém cota minhoca. Foi exatamente o que
    aconteceu na primeira rodada com preço real.

    Chance 1.0 é a marca do que sai sempre. Quando nada sai sempre, sobra a
    saída de maior valor esperado: é a que a pessoa está indo buscar.
    """
    candidatas = [o for o in farmable.outputs if o.role in ("harvest", "product", "grown")]
    if not candidatas:
        return set()
    certas = {o.id for o in candidatas if float(o.chance) >= 1.0}
    if certas:
        return certas
    melhor = max(candidatas, key=lambda o: (o.amount_min + o.amount_max) / 2 * float(o.chance))
    return {melhor.id}


def _focus_total(farmable: Farmable, tipo: PlanKind) -> int:
    """Focus gasto no plano inteiro.

    Adulto que produz leite não tem campo de Focus no dump, e ausência não vira
    zero por chute: aqui zero significa "o dump não cobra Focus por este ciclo",
    que é o que ele de fato diz ao não trazer o campo.
    """
    if farmable.focus_cost is None:
        return 0
    if tipo is PlanKind.PRODUCT:
        return 0
    return farmable.focus_cost * max(1, farmable.max_cycles or 1)


def _roteiro(cidades: list[str], compras: MaterialSourcing) -> SourcingOut:
    distintas = sorted(set(cidades))
    return SourcingOut(
        mode=str(compras.mode), cities_involved=len(distintas), cities=distintas
    )


def _plano(
    farmable, item, tipo, entradas_out, saidas_out, cidades, compras,
    buy_location: str, sell_location: str, economia: FarmEconomics, liquidez: float | None,
) -> FarmPlanOut:
    return FarmPlanOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name),
        tier=item.tier,
        station=farmable.station,
        station_label=STATION_LABELS.get(farmable.station, farmable.station),
        kind=str(tipo),
        buy_location=buy_location,
        sell_location=sell_location,
        focus_cycles=farmable.max_cycles,
        liquidity_units_per_day=liquidez,
        npc_silver_cost=farmable.npc_silver_cost,
        inputs=entradas_out,
        outputs=saidas_out,
        material_sourcing=_roteiro(cidades, compras),
        economics=FarmEconomicsOut(
            known=economia.known,
            reason=economia.reason,
            kind=economia.kind,
            cycle_seconds=economia.cycle_seconds,
            cycle_days=economia.cycle_days,
            focus_cost=economia.focus_cost,
            input_cost=economia.input_cost,
            gross_revenue=economia.gross_revenue,
            sale_revenue_net=economia.sale_revenue_net,
            market_fees=economia.market_fees,
            profit_per_cycle=economia.profit_per_cycle,
            profit_per_day=economia.profit_per_day,
            profit_per_focus=economia.profit_per_focus,
            focus_per_day=economia.focus_per_day,
            margin_pct=economia.margin_pct,
            roi_pct=economia.roi_pct,
            outputs_without_price=economia.outputs_without_price,
        ),
    )


def _plano_desconhecido(
    farmable, item, tipo, ciclo, entradas_out, cidades, compras,
    buy_location: str, sell_location: str, motivo: str,
) -> FarmPlanOut:
    """O plano continua na tela, com o motivo.

    Sumir deixaria um buraco sem explicação: o usuário não saberia que existe
    uma criação ali, nem o que falta para avaliá-la.
    """
    economia = FarmEconomics(
        known=False,
        reason=motivo,
        kind=str(tipo),
        cycle_seconds=ciclo,
        cycle_days=round(ciclo / 86_400, 4) if ciclo else 0.0,
        focus_cost=_focus_total(farmable, tipo),
    )
    return _plano(
        farmable, item, tipo, entradas_out, [], cidades, compras,
        buy_location, sell_location, economia, None,
    )


def _vazio(
    server, buy_location, sell_location, sort_by, sourcing_mode, params, sort_desc=True
) -> FarmingResponse:
    return FarmingResponse(
        server=server,
        buy_location=buy_location,
        sell_location=sell_location,
        sort_by=sort_by,
        sort_dir="desc" if sort_desc else "asc",
        sourcing_mode=str(sourcing_mode),
        total=0,
        params=params,
        generated_at=datetime.now(UTC).isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
        stations=[],
        plans=[],
    )
