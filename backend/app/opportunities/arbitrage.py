"""Motor de arbitragem entre cidades.

Compara o preço de um mesmo item em locais diferentes do **mesmo servidor** e
monta as operações viáveis. O cálculo em si vive em `calculations/`; aqui fica a
política: quais pares considerar, o que descartar antes de calcular, e como
ordenar.

Três filtros aplicados **antes** de calcular, porque calcular lixo e depois
esconder é desperdício e convida a bug:

1. Preço velho demais não vira oportunidade. Recomendar compra sobre cotação de
   ontem é como recomendar uma ação com a cotação da semana passada.
2. Black Market fica fora por padrão: a semântica de ordens é invertida e ainda
   não foi validada empiricamente (docs/02-aodp.md).
3. Origem e destino precisam ser diferentes.
"""

from dataclasses import dataclass

from app.calculations.fees import FeeProfile, Strategy, TradeEconomics, compute_trade
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
    include_black_market: bool = False,
    min_profit: float = 0.0,
) -> list[ArbitrageOpportunity]:
    """Monta as oportunidades a partir das linhas de preço já carregadas.

    Recebe tudo em memória de propósito: a comparação é cruzada entre locais e
    fazer isso no banco exigiria um self-join que fica ilegível e lento.
    """
    por_item: dict[tuple[int, int], list[PriceRow]] = {}
    for row in rows:
        if not include_black_market and row.location.kind == "black_market":
            continue
        por_item.setdefault((row.item.id, row.price.quality), []).append(row)

    oportunidades: list[ArbitrageOpportunity] = []

    for (_item_id, quality), grupo in por_item.items():
        if len(grupo) < 2:
            continue

        for origem in grupo:
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

                score = compute_score(
                    ScoreInputs(
                        profit=economia.net_profit,
                        margin_pct=economia.margin_pct,
                        roi_pct=economia.roi_pct,
                        freshness_seconds=pior_idade,
                        liquidity_units_per_day=liquidez,
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
