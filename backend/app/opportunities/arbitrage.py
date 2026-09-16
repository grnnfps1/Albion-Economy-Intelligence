"""Motor de arbitragem entre cidades.

Compara o preço de um mesmo item em locais diferentes do **mesmo servidor** e
monta as operações viáveis. O cálculo em si vive em `calculations/`; aqui fica a
política: quais pares considerar, o que descartar antes de calcular, e como
ordenar.

Três filtros aplicados **antes** de calcular, porque calcular lixo e depois
esconder é desperdício e convida a bug:

1. Preço velho demais não vira oportunidade. Recomendar compra sobre cotação de
   ontem é como recomendar uma ação com a cotação da semana passada.
2. Black Market entra como **destino de venda**, nunca como origem de compra.
   A validação de 16/09/2026 (docs/02-aodp.md) mostrou que ele preenche
   `buy_price_max` em 40 de 40 equipamentos, com orientação normal — vender
   nele é igual a vender numa cidade. Comprar lá não foi medido, e perna não
   medida não entra.
3. Origem e destino precisam ser diferentes.

Toda operação sai com a **zona da rota** e o lucro ajustado ao risco ao lado do
bruto. Uma rota que passa por Caerleon ou pelo Black Market atravessa zona
aberta, e o spread maior dela é pagamento por esse risco — não vantagem.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.calculations.fees import FeeProfile, Strategy, TradeEconomics, compute_trade
from app.calculations.risk import (
    RiskAdjusted,
    RiskProfile,
    Zone,
    adjust_for_risk,
    distance_factor,
)
from app.calculations.scoring import ScoreInputs, ScoreResult, compute_score
from app.models.catalog import Item
from app.models.market import MarketPrice
from app.models.reference import Location
from app.repositories.liquidity import LiquiditySignal


@dataclass(frozen=True)
class PriceRow:
    price: MarketPrice
    item: Item
    location: Location
    liquidity: LiquiditySignal | None = None


@dataclass(frozen=True)
class ArbitrageOpportunity:
    item: Item
    quality: int
    origin: Location
    destination: Location
    strategy: Strategy
    buy_price: int
    sell_price: int
    economics: TradeEconomics
    score: ScoreResult
    risk: RiskAdjusted
    worst_age_seconds: int
    liquidity_units_per_day: float | None


def _age(price: MarketPrice, now, field: str) -> int | None:
    value = getattr(price, field)
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def build_opportunities(
    rows: list[PriceRow],
    now,
    fees: FeeProfile,
    weights: dict[str, float],
    strategy: Strategy = Strategy.FAST,
    quantity: int = 100,
    transport_cost_per_unit: float = 0.0,
    max_age_seconds: int = 21_600,
    include_black_market: bool = True,
    min_profit: float = 0.0,
    zone_of: Callable[[str, str], Zone] | None = None,
    risk: RiskProfile | None = None,
) -> list[ArbitrageOpportunity]:
    """Monta as oportunidades a partir das linhas de preço já carregadas.

    Recebe tudo em memória de propósito: a comparação é cruzada entre locais e
    fazer isso no banco exigiria um self-join que fica ilegível e lento.
    """
    perfil = risk or RiskProfile()
    zona_de = zone_of or (lambda _o, _d: Zone.BLUE)

    por_item: dict[tuple[int, int], list[PriceRow]] = {}
    for row in rows:
        por_item.setdefault((row.item.id, row.price.quality), []).append(row)

    oportunidades: list[ArbitrageOpportunity] = []

    for (_item_id, quality), grupo in por_item.items():
        if len(grupo) < 2:
            continue

        for origem in grupo:
            # Comprar no Black Market não foi validado: ele entra só como
            # destino. Habilitar a perna de compra exigiria a medição própria
            # descrita em docs/02-aodp.md.
            if origem.location.kind == "black_market":
                continue

            # Comprar consome ordem de venda na origem.
            buy_price = (
                origem.price.sell_price_min
                if strategy is Strategy.FAST
                else origem.price.buy_price_max
            )
            idade_compra = _age(
                origem.price,
                now,
                "sell_price_min_date" if strategy is Strategy.FAST else "buy_price_max_date",
            )
            if buy_price is None or idade_compra is None or idade_compra > max_age_seconds:
                continue

            for destino in grupo:
                if destino.location.id == origem.location.id:
                    continue
                if not include_black_market and destino.location.kind == "black_market":
                    continue

                # Vender entrega para ordem de compra no destino.
                sell_price = (
                    destino.price.buy_price_max
                    if strategy is Strategy.FAST
                    else destino.price.sell_price_min
                )
                idade_venda = _age(
                    destino.price,
                    now,
                    "buy_price_max_date" if strategy is Strategy.FAST else "sell_price_min_date",
                )
                if sell_price is None or idade_venda is None or idade_venda > max_age_seconds:
                    continue
                if sell_price <= buy_price:
                    continue

                economia = compute_trade(
                    buy_price, sell_price, fees, strategy, quantity, transport_cost_per_unit
                )
                if economia.known and (economia.net_profit or 0) < min_profit:
                    continue

                # A idade que importa é a da ponta mais velha: a operação só é
                # tão confiável quanto o pior dos dois preços.
                pior_idade = max(idade_compra, idade_venda)

                # Liquidez do destino: é lá que a mercadoria precisa escoar.
                liquidez = (
                    destino.liquidity.units_per_day
                    if destino.liquidity and destino.liquidity.known
                    else None
                )

                zona = zona_de(origem.location.slug, destino.location.slug)
                risco = adjust_for_risk(
                    economia.net_profit, economia.investment, zona, perfil
                )

                score = compute_score(
                    ScoreInputs(
                        # O lucro que entra no score é o **ajustado**: ranquear
                        # pelo bruto colocaria a rota de zona vermelha no topo
                        # justamente por ela pagar o prêmio do risco.
                        profit=(
                            risco.expected_profit
                            if risco.expected_profit is not None
                            else economia.net_profit
                        ),
                        margin_pct=economia.margin_pct,
                        roi_pct=economia.roi_pct,
                        freshness_seconds=pior_idade,
                        liquidity_units_per_day=liquidez,
                        loss_probability=risco.loss_probability,
                        distance_factor=distance_factor(zona),
                    ),
                    weights,
                )

                oportunidades.append(
                    ArbitrageOpportunity(
                        item=origem.item,
                        quality=quality,
                        origin=origem.location,
                        destination=destino.location,
                        strategy=strategy,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        economics=economia,
                        score=score,
                        risk=risco,
                        worst_age_seconds=pior_idade,
                        liquidity_units_per_day=liquidez,
                    )
                )

    # Sem score calculável, ordena pelo spread bruto — mas essas entradas vêm
    # marcadas como UNKNOWN na resposta e nunca são apresentadas como lucro.
    oportunidades.sort(
        key=lambda o: (o.score.score if o.score.score is not None else -1), reverse=True
    )
    return oportunidades
