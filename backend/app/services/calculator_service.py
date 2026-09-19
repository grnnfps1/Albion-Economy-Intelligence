"""Calculador de crafting: uma família por vez, todas as combinações.

`/crafting` responde *onde gasto meu Focus hoje* — é um ranking, ordenado, que
mistura famílias e mostra só o topo.

Este serviço responde outra coisa: *quanto rende esta família se eu mexer nos
preços*. São as 27 linhas de uma linha de recurso (T2.0, T3.0 e T4.0–T8.4), na
ordem do jogo, com preço editável e recálculo imediato. As duas perguntas
convivem porque são de fato diferentes — quem monta produção quer a tabela
inteira; quem tem 10 mil de Focus sobrando quer o topo do ranking.

## O que é herdado e o que é novo

A aritmética é a de sempre: `compute_craft` com estratégia **PACIENTE**, que é
o que corresponde a criar ordem de venda — paga imposto **e** setup fee, e paga
o setup mesmo se a ordem não executar. No padrão isso dá 6,5% sobre a receita
bruta, que é exatamente o que a planilha de referência cobra na coluna "Taxa de
Venda" (conferido: 6,5000% em todas as linhas).

O que é novo é a **lista de compras** — quanto comprar de cada material para
uma quantidade alvo, com o retorno reduzindo o consumo — e a **previsão**:
lucro total, capital imobilizado e em quantos dias a quantidade escoa.

## Duas diferenças conscientes em relação à planilha

**O retorno só desconta material elegível.** A planilha aplica a taxa sobre
tudo; nós excluímos o que não volta, como token de facção (regra da fase 7).
Errar para menos retorno é o lado conservador.

**A margem sai nas duas definições.** A "Margem de Lucro" da planilha é lucro ÷
custo de produção — que é ROI, não margem. A nossa é sobre receita bruta. As
duas vão na resposta, rotuladas, porque margem alta com ROI baixo é armadilha
de capital parado.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.crafting import MaterialCost, compute_craft
from app.calculations.fees import Strategy
from app.calculations.returns import Activity
from app.calculations.shopping import RESSALVA_DO_RETORNO, shopping_line
from app.calculations.station import NUTRITION_PER_ITEM_VALUE
from app.catalog.icons import item_icon_url
from app.core.config import get_settings
from app.models.catalog import Item
from app.models.manual_price import KIND_SELL
from app.repositories import market as market_repo
from app.repositories import recipes_repo
from app.repositories.liquidity import liquidity_by_item_location
from app.repositories.reference import list_locations
from app.schemas.calculator import (
    CalcMaterialOut,
    CalcParamsUsed,
    CalcRowOut,
    CalculatorResponse,
    CityQuoteOut,
    PriceRangeOut,
    ReturnOptionOut,
)
from app.schemas.crafting import SpecializationUsed
from app.services.arbitrage_service import resolve_fees
from app.services.manual_price_service import load_manual_overlay
from app.services.return_service import ISLAND_KINDS, load_return_policy, return_out
from app.services.sourcing import SourcingMode, load_material_sourcing
from app.services.specialization_service import load_specialization_policy, spec_out
from app.services.station_service import (
    StationFeePolicy,
    item_value_lookup,
    load_station_fee_policy,
)

DATA_SOURCE_NOTE = (
    "Os preços vêm da coleta comunitária do AODP e podem estar velhos. Onde você "
    "editar, o seu preço vence e fica marcado — é a mesma sobrescrita da fase 17, "
    "e ela envelhece junto."
)

REFINED_SUBCATEGORY = "refinedresources"
RAW_SUBCATEGORY = "resources"
TOKEN_SUBCATEGORY = "cityresources"
TOKEN_PREFIX = "T1_FACTION_"

# Papel do material na receita, e a ordem em que os papéis aparecem na tela.
#
# A ordem do dump **não** é estável: `T8_LEATHER` sem token lista
# `resources, refinedresources`; com token lista
# `resources, cityresources, refinedresources`. Renderizar nessa ordem faria o
# token cair na coluna 2 numa linha e o refinado na outra, e a coluna deixaria
# de significar a mesma coisa em todas as linhas — que é justamente o que
# permite comparar o preço do pelego de cima a baixo.
ROLE_RAW = "bruto"
ROLE_REFINED = "refinado"
ROLE_TOKEN = "token"
ROLE_OTHER = "outro"
ROLE_ORDER = (ROLE_RAW, ROLE_REFINED, ROLE_TOKEN, ROLE_OTHER)


def role_of(item) -> str:
    """Papel do material, pela subcategoria do catálogo.

    O token é reconhecido pelos **dois** sinais — subcategoria `cityresources`
    e prefixo `T1_FACTION_` — porque só o prefixo já bastaria hoje e é o tipo
    de coisa que muda de nome num patch.
    """
    if item.subcategory_code == TOKEN_SUBCATEGORY or item.unique_name.startswith(TOKEN_PREFIX):
        return ROLE_TOKEN
    if item.subcategory_code == RAW_SUBCATEGORY:
        return ROLE_RAW
    if item.subcategory_code == REFINED_SUBCATEGORY:
        return ROLE_REFINED
    return ROLE_OTHER

# As cinco linhas de recurso. Pedra é a exceção que o dump impõe: ela **não tem
# variante encantada**, então tem 7 linhas onde as outras têm 27. Confirmado no
# dump e no catálogo importado.
FAMILIES = ("LEATHER", "CLOTH", "PLANKS", "METALBAR", "STONEBLOCK")

# As colunas por onde a tabela pode ser ordenada.
#
# `tier` é o padrão e não é um estado à parte: é uma coluna como as outras, só
# que a que a tela abre. Ela é o motivo de a tabela existir neste formato —
# comparar T5.2 com T6.2 na vertical — e por isso o terceiro clique de qualquer
# coluna volta para ela.
SORTABLE = ("tier", "profit", "total_investment", "production_cost")
DEFAULT_SORT = "tier"


def _ordena(linhas: list[CalcRowOut], sort_by: str, desc: bool) -> list[CalcRowOut]:
    """Ordena as linhas. Comparar lucro é aritmética de negócio, e mora aqui.

    ## Linha sem cálculo vai para o fim — exceto por tier

    Uma linha bloqueada por falta de cotação **não tem lucro**. Não é lucro
    zero: é lucro desconhecido, e desconhecido não compete com número (regra 1).
    Deixá-la participar da ordenação por valor a colocaria no meio do ranking
    como se fosse a pior — ou, num `desc` com `None` tratado como zero, acima de
    todas as que dão prejuízo.

    **Por tier é o contrário, e a diferença importa.** Ali a posição é
    intrínseca ao item, não ao resultado: jogar T8.4 para o fim por falta de
    cotação quebraria justamente a sequência que essa ordenação existe para
    mostrar.
    """
    if sort_by == "tier":
        # Pelo par (tier, encantamento), nunca pelo rótulo: "T5.4" e "T6.0"
        # comparados como texto já funcionam por coincidência, mas "T10.0"
        # viria antes de "T2.0" no dia em que existir.
        return sorted(
            linhas,
            key=lambda linha: (linha.tier or 0, linha.enchantment),
            reverse=desc,
        )

    def chave(linha: CalcRowOut):
        valor = getattr(linha, sort_by, None)
        # O primeiro item da tupla separa conhecido de desconhecido **antes** do
        # valor, e não é invertido pelo `reverse`: por isso o sinal entra no
        # segundo, e as bloqueadas ficam no fim nas duas direções.
        return (valor is None, -(valor or 0.0) if desc else (valor or 0.0))

    return sorted(linhas, key=chave)

_FAMILIA = re.compile(r"^T\d_([A-Z]+?)(?:_LEVEL\d+)?(?:@\d)?$")


def family_of(unique_name: str) -> str | None:
    match = _FAMILIA.match(unique_name)
    return match.group(1) if match else None


def _age(value: datetime | None, now: datetime) -> int | None:
    return None if value is None else max(0, int((now - value).total_seconds()))


def _rotulo_de_variante(receita, catalogo) -> str:
    tem_token = any(
        m.item_id in catalogo and role_of(catalogo[m.item_id]) == ROLE_TOKEN
        for m in receita.materials
    )
    return "com token de faccao" if tem_token else "sem token"


async def build_calculator(
    session: AsyncSession,
    *,
    server: str,
    family: str,
    buy_location: str,
    sell_location: str,
    quantity: int,
    station_fee_per_100_nutrition: float | None,
    setup_fee_pct: float | None,
    sales_tax_pct: float | None,
    premium: bool | None,
    return_rate: float | None,
    use_focus: bool,
    daily_production_bonus: float,
    produce_on_island: bool = False,
    spec_levels: dict[str, int] | None,
    spec_item_levels: dict[str, int] | None,
    # Só ecoa em `params`: nenhuma coluna desta tela o usa. O orçamento de
    # Focus limita o ranking de `/focus`, não a tabela de uma família — e por
    # isso o campo saiu do painel de preferências daqui.
    focus_per_day: float | None,
    sort_by: str = DEFAULT_SORT,
    sort_desc: bool = False,
    user_id: str | None = None,
    sourcing_mode: SourcingMode = SourcingMode.SINGLE_CITY,
    max_age_seconds: int | None = None,
) -> CalculatorResponse:
    familia = (family or FAMILIES[0]).upper()
    if familia not in FAMILIES:
        familia = FAMILIES[0]

    now = datetime.now(UTC)
    quantidade = max(1, quantity)
    if max_age_seconds is None:
        max_age_seconds = get_settings().freshness_stale_seconds

    fees, resumo_taxas = await resolve_fees(session, setup_fee_pct, sales_tax_pct, premium)
    retornos = await load_return_policy(session)
    spec = await load_specialization_policy(session, spec_levels, item_levels=spec_item_levels)
    nomes_de_cidade = {loc.slug: loc.display_name for loc in await list_locations(session)}

    # Os itens da família, em ordem de jogo: T2.0, T3.0, T4.0…T8.4.
    itens = list(
        (
            await session.scalars(
                select(Item)
                .where(Item.subcategory_code == REFINED_SUBCATEGORY, Item.active.is_(True))
                .order_by(Item.tier, Item.enchantment)
            )
        ).all()
    )
    itens = [i for i in itens if family_of(i.unique_name) == familia]

    faltando = list(resumo_taxas.missing)
    taxa_estacao = await load_station_fee_policy(
        session, lambda _n: None, station_fee_per_100_nutrition
    )
    faltando.extend(taxa_estacao.missing())

    ordenacao = sort_by if sort_by in SORTABLE else DEFAULT_SORT
    params = CalcParamsUsed(
        quantity=quantidade,
        sort_by=ordenacao,
        sort_dir="desc" if sort_desc else "asc",
        sourcing=str(sourcing_mode),
        strategy=str(Strategy.PATIENT),
        station_fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        nutrition_per_item_value=NUTRITION_PER_ITEM_VALUE,
        focus_per_day=focus_per_day,
        fees=resumo_taxas,
        specialization=SpecializationUsed(**spec_out(spec)),
        complete=not faltando,
        missing=faltando,
    )

    if not itens:
        return _vazio(server, familia, buy_location, sell_location, params, now)

    # Receitas: todas as variantes, para o motor poder comparar — e só as que
    # esta família alcança. Pedir as 12.917 do jogo para usar as poucas de uma
    # linha de recurso era o gargalo desta tela desde a fase 19, medido em
    # `docs/07-desempenho.md`: 93% do tempo da requisição numa consulta cujo
    # resultado era descartado quase inteiro.
    todas = await recipes_repo.recipes_for_chain(session, [i.id for i in itens])
    receitas: dict[int, list] = {}
    for receita in todas:
        receitas.setdefault(receita.output_item_id, []).append(receita)

    ids = {i.id for i in itens}
    for item in itens:
        for receita in receitas.get(item.id) or []:
            ids.update(m.item_id for m in receita.materials)

    catalogo = await recipes_repo.load_items(session, sorted(ids))
    taxa_estacao = StationFeePolicy(
        fee_per_100_nutrition=taxa_estacao.fee_per_100_nutrition,
        item_value_of=item_value_lookup(catalogo),
    )

    manual = await load_manual_overlay(session, user_id, server, now=now)

    # Preço de venda do item final, na cidade onde se vende.
    linhas, _ = await market_repo.search_prices(
        session, server_code=server, location_slugs=[sell_location], limit=50_000
    )
    precos_venda: dict[str, tuple[int | None, int | None]] = {}
    for price, item, _loc in linhas:
        # PACIENTE cria ordem de venda: o preço de referência é `sell_price_min`.
        precos_venda.setdefault(
            item.unique_name, (price.sell_price_min, _age(price.sell_price_min_date, now))
        )

    nomes_materiais = sorted(
        {
            catalogo[m.item_id].unique_name
            for item in itens
            for receita in receitas.get(item.id) or []
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
        manual=manual,
    )
    sinais = await liquidity_by_item_location(session, server, sorted(ids))

    # O bônus de refino segue o recurso, e o recurso é o mesmo da família
    # inteira — basta resolver uma vez.
    # Onde se **produz**, que não é onde se compra: quem produz na ilha compra
    # os materiais numa cidade e carrega. A ilha zera a base de cidade.
    local_de_producao = "island" if produce_on_island else buy_location
    retorno, melhor_cidade = retornos.resolve(
        Activity.REFINING,
        itens[0].unique_name,
        city_slug=local_de_producao,
        use_focus=use_focus,
        daily_bonus=daily_production_bonus,
        override=return_rate,
    )

    # O retorno de cada local para esta família, com os mesmos Focus e bônus do
    # dia. O motor já sabia disto desde a fase 20 e só contava **depois** do
    # cálculo — quem estava em Caerleon sem Focus via 27 linhas vermelhas e
    # nenhuma pista de que trocar de cidade resolveria.
    locais = await list_locations(session, only_active=False)
    opcoes = retornos.options(
        Activity.REFINING,
        itens[0].unique_name,
        [
            (local.slug, local.display_name, local.kind in ISLAND_KINDS)
            for local in locais
            if local.kind != "black_market"
        ],
        use_focus=use_focus,
        daily_bonus=daily_production_bonus,
        override=return_rate,
    )
    melhor_taxa = max((o.rate for o in opcoes if o.rate is not None), default=None)
    opcoes_out = [
        ReturnOptionOut(
            slug=o.slug,
            name=o.name,
            rate=o.rate,
            has_city_bonus=o.has_city_bonus,
            is_island=o.is_island,
            is_current=o.slug == local_de_producao,
            is_best=o.rate is not None and o.rate == melhor_taxa,
        )
        for o in opcoes
    ]

    linhas_out = [
        _linha(
            item, receitas, catalogo, compras, manual, precos_venda, sinais,
            taxa_estacao, spec, fees, retorno.rate, quantidade,
            sell_location, now,
        )
        for item in itens
    ]

    linhas_out = _ordena(linhas_out, ordenacao, sort_desc)

    return CalculatorResponse(
        server=server,
        family=familia,
        families=list(FAMILIES),
        buy_location=buy_location,
        sell_location=sell_location,
        rows=linhas_out,
        material_return=return_out(
            retorno,
            melhor_cidade,
            nomes_de_cidade,
            components=retornos.components,
            activity=Activity.REFINING,
            # A parcela do bônus é rotulada com a cidade que **dá** o bônus,
            # não com a que está em uso. Quando ela não se aplica, é o nome da
            # outra cidade que informa: "refino em Martlock 40% (não)" diz o
            # que fazer; "refino em Caerleon 40% (não)" não diz nada.
            city_label=nomes_de_cidade.get(
                melhor_cidade.city_slug or "", melhor_cidade.city_slug
            ),
        ),
        return_options=opcoes_out,
        params=params,
        return_note=RESSALVA_DO_RETORNO,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
    )


def _linha(
    item, receitas, catalogo, compras, manual, precos_venda, sinais,
    taxa_estacao, spec, fees, taxa_retorno, quantidade,
    sell_location, now,
) -> CalcRowOut:
    rotulo = f"T{item.tier}.{item.enchantment}"
    base = CalcRowOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name),
        tier=item.tier,
        enchantment=item.enchantment,
        tier_label=rotulo,
    )

    # Preço de venda: manual vence o coletado, e diz que venceu.
    coletado, idade = precos_venda.get(item.unique_name, (None, None))
    cotacao_manual = manual.quote(item.unique_name, sell_location, 1, KIND_SELL)
    venda = coletado
    if cotacao_manual is not None and cotacao_manual.applies:
        venda = cotacao_manual.price
        base.sell_price_is_manual = True
        base.sell_collected_price = coletado
        idade = cotacao_manual.age_seconds
    base.sell_price = venda
    base.sell_age_seconds = idade

    sinal = next((v for (i, _l, _q), v in sinais.items() if i == item.id and v.known), None)
    base.liquidity_units_per_day = sinal.units_per_day if sinal else None

    # Quantos dias a quantidade leva para escoar **não depende do lucro**: sai
    # do giro medido e da quantidade pedida, e os dois existem mesmo quando a
    # taxa da estação falta. Ficava dentro do ramo `known` e por isso sumia
    # justamente nas linhas em que o usuário mais queria alguma informação.
    if sinal and sinal.known and sinal.units_per_day:
        base.days_to_sell = round(quantidade / sinal.units_per_day, 1)

    variantes = receitas.get(item.id) or []
    if not variantes:
        base.reason = "sem receita no dump"
        return base

    # Custeia cada variante e fica com a mais barata — mesma regra do motor de
    # refino. A descartada vai na linha, porque com token o custo muda muito.
    avaliadas = []
    incompletas = []
    for receita in variantes:
        materiais = _materiais(receita, catalogo, compras, manual)
        if materiais is None:
            continue
        # Material sem cotação **não** custa zero. Tratá-lo como zero fazia a
        # variante incompleta parecer a mais barata e vencer a comparação —
        # custo parcial não é custo menor, é custo desconhecido (regra 1).
        if any(not m.known for m in materiais):
            incompletas.append((receita, materiais))
            continue
        avaliadas.append((sum(m.gross_cost or 0 for m in materiais), receita, materiais))

    if not avaliadas:
        # Nenhuma variante tem todos os preços. A resposta usa a primeira
        # incompleta para que `compute_craft` nomeie **qual** material falta,
        # em vez de dizer só "sem cotação".
        if incompletas:
            receita, materiais = incompletas[0]
            economia = compute_craft(
                materials=materiais, sell_price=venda, fees=fees,
                return_rate=taxa_retorno,
                station_fee=taxa_estacao.fee_of(item.unique_name),
                output_quantity=receita.output_quantity,
                focus_cost=spec.focus_cost_of(item.unique_name, receita.focus_cost),
                crafts=quantidade, strategy=Strategy.PATIENT,
            )
            base.materials = _materiais_out(
                receita, catalogo, compras, manual, materiais, quantidade, taxa_retorno
            )
            _explica(base, economia)
        else:
            base.reason = "sem cotação para os materiais"
            base.blocker = "cotacao"
            base.blocked_data = [base.reason]
        return base

    avaliadas.sort(key=lambda a: a[0])
    _custo, receita, materiais = avaliadas[0]
    base.variant_label = _rotulo_de_variante(receita, catalogo)
    if len(avaliadas) > 1:
        base.alternative_cost = round(avaliadas[1][0], 2)
        base.alternative_label = _rotulo_de_variante(avaliadas[1][1], catalogo)

    focus = spec.focus_cost_of(item.unique_name, receita.focus_cost)
    economia = compute_craft(
        materials=materiais,
        sell_price=venda,
        fees=fees,
        return_rate=taxa_retorno,
        station_fee=taxa_estacao.fee_of(item.unique_name),
        output_quantity=receita.output_quantity,
        focus_cost=focus,
        crafts=quantidade,
        # Ordem de venda: paga imposto **e** setup, e o setup mesmo se não
        # executar. É o que a planilha cobra e o que o jogador de fato paga.
        strategy=Strategy.PATIENT,
    )

    base.materials = _materiais_out(
        receita, catalogo, compras, manual, materiais, quantidade, taxa_retorno
    )
    base.focus_cost = economia.focus_cost

    if not economia.known:
        _explica(base, economia)
        return base

    receita_bruta = (venda or 0) * quantidade * max(1, receita.output_quantity)

    base.known = True
    base.material_cost = economia.material_cost_net
    base.material_cost_gross = economia.material_cost_gross
    base.returned_value = economia.returned_value
    base.station_fee = economia.station_fee
    base.sale_fee = economia.market_fees
    base.production_cost = economia.production_cost
    base.gross_revenue = round(receita_bruta, 2)
    base.profit = economia.profit
    # As três razões vêm prontas de `compute_craft`, calculadas antes de
    # qualquer arredondamento. Refazê-las aqui a partir dos campos já
    # arredondados fazia margem e ROI variarem com a quantidade.
    base.margin_pct = economia.margin_pct
    base.margin_on_cost_pct = economia.margin_on_cost_pct
    base.profit_per_focus = economia.profit_per_focus

    # Previsão: o lucro já é da quantidade pedida, porque `crafts=quantidade`.
    base.total_profit = economia.profit
    base.total_investment = round(
        (economia.material_cost_gross or 0) + (economia.station_fee or 0), 2
    )

    return base


def _intervalo(faixa) -> PriceRangeOut | None:
    """O intervalo entre cidades, pronto para a tela.

    `None` quando não há cotação nenhuma: aí a linha já vai dizer que falta
    preço, e um intervalo vazio ao lado só repetiria a ausência.
    """
    if not faixa.cities:
        return None
    return PriceRangeOut(
        cities=[
            CityQuoteOut(
                location_slug=c.location_slug,
                location_name=c.location_name,
                unit_price=c.unit_price,
                age_seconds=c.age_seconds,
                is_fresh=c.is_fresh,
                is_manual=c.is_manual,
                is_chosen=c.is_chosen,
            )
            for c in faixa.cities
        ],
        min_price=faixa.min_price,
        max_price=faixa.max_price,
        spread=faixa.spread,
        spread_pct=faixa.spread_pct,
        fresh_city_count=faixa.fresh_city_count,
        comparable=faixa.comparable,
    )


def _explica(base: CalcRowOut, economia) -> None:
    """Traduz o impedimento para a linha, separando o que é de quem.

    A distinção não é cosmética. Falta de **parâmetro** é global — vale para as
    27 linhas de uma vez e some quando o usuário preenche um campo. Falta de
    **cotação** é da linha, e nenhum campo a resolve: ou o mercado ganha uma
    ordem, ou se compra em outra cidade. Mostrar as duas com o mesmo traço
    fazia a tela responder "não sei" a duas perguntas diferentes.
    """
    base.reason = economia.reason
    base.blocked_data = list(economia.missing_data)
    if economia.missing_data and economia.missing:
        base.blocker = "ambos"
    elif economia.missing_data:
        base.blocker = "cotacao"
    elif economia.missing:
        base.blocker = "parametro"


def _materiais(receita, catalogo, compras, manual) -> list[MaterialCost] | None:
    materiais: list[MaterialCost] = []
    for m in receita.materials:
        if m.item_id not in catalogo:
            return None
        material = catalogo[m.item_id]
        escolha = compras.choose(material.unique_name)
        cotacao = escolha.quote if escolha.known else None
        materiais.append(
            MaterialCost(
                unique_name=material.unique_name,
                display_name=material.display_name_pt or material.display_name_en,
                quantity=m.quantity,
                unit_price=cotacao.unit_price if cotacao else None,
                is_returnable=m.is_returnable,
                location=cotacao.location_name if cotacao else None,
                age_seconds=cotacao.age_seconds if cotacao else None,
            )
        )
    return materiais


def _materiais_out(
    receita, catalogo, compras, manual, materiais, quantidade, taxa_retorno
) -> list[CalcMaterialOut]:
    saida: list[CalcMaterialOut] = []
    for m, custo in zip(receita.materials, materiais, strict=False):
        material = catalogo[m.item_id]
        papel = role_of(material)
        escolha = compras.choose(material.unique_name)
        cotacao = escolha.quote if escolha.known else None

        # Token de facção não volta: a lista de compras não pode descontá-lo.
        taxa = taxa_retorno if m.is_returnable else 0.0
        linha = shopping_line(material.unique_name, quantidade, m.quantity, taxa)

        saida.append(
            CalcMaterialOut(
                item=material.unique_name,
                item_name=material.display_name_pt or material.display_name_en,
                icon_url=item_icon_url(material.unique_name),
                quantity=m.quantity,
                is_returnable=m.is_returnable,
                role=papel,
                unit_price=custo.unit_price,
                price_is_manual=bool(cotacao and getattr(cotacao, "is_manual", False)),
                age_seconds=custo.age_seconds,
                location=custo.location,
                is_alternate_city=escolha.is_alternate if escolha.known else False,
                buy_units=linha.units,
                gross_units=linha.gross,
                saved_by_return=linha.saved,
                price_range=_intervalo(compras.range_of(material.unique_name)),
            )
        )
    # Ordena por papel, não pela ordem do dump. `sorted` é estável, então dois
    # materiais do mesmo papel mantêm a ordem em que a receita os trouxe.
    return sorted(saida, key=lambda mat: ROLE_ORDER.index(mat.role))


def _vazio(server, familia, buy_location, sell_location, params, now) -> CalculatorResponse:
    return CalculatorResponse(
        server=server,
        family=familia,
        families=list(FAMILIES),
        buy_location=buy_location,
        sell_location=sell_location,
        rows=[],
        params=params,
        return_note=RESSALVA_DO_RETORNO,
        generated_at=now.isoformat(),
        data_source_note=DATA_SOURCE_NOTE,
    )
