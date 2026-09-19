"""Montagem das respostas de mercado.

A idade do dado é calculada aqui, não no banco e não no frontend: o limiar de
frescor é configuração e pode mudar sem migration nem deploy do frontend.
"""

from datetime import datetime

from app.calculations.statistics import percentage_change
from app.catalog.icons import item_icon_url
from app.core.config import Settings
from app.core.freshness import classify, data_age_seconds
from app.models.catalog import Item
from app.models.manual_price import KIND_BUY, KIND_SELL
from app.models.market import MarketPrice
from app.models.reference import Location
from app.repositories.liquidity import LiquiditySignal
from app.schemas.market import LiquidityOut, MarketPriceOut, PriceField
from app.services.manual_price_service import ManualPriceOverlay, ManualQuote

DATA_SOURCE_NOTE = (
    "Preços vêm da coleta comunitária do Albion Online Data Project: dependem de "
    "jogadores terem aberto o mercado no jogo. Sem dado não significa preço baixo."
)


def _field(
    value: int | None,
    date: datetime | None,
    now: datetime,
    settings: Settings,
    manual: ManualQuote | None = None,
) -> PriceField:
    """Um campo de preço, já resolvido entre o coletado e o manual.

    Quando o preço manual vale, ele entra como `value` e a idade passa a ser a
    de **quando o usuário informou** — não a da cotação que ele substituiu. O
    coletado vai junto em `collected_value`, porque ver os dois lado a lado é o
    que permite alguém perceber que digitou um zero a mais.

    Quando o preço manual existe mas expirou, o coletado volta e a linha carrega
    `manual_expired`: ignorar em silêncio faria o usuário achar que o preço que
    ele informou continua valendo.
    """
    if manual is not None and manual.applies:
        return PriceField(
            value=manual.price,
            age_seconds=manual.age_seconds,
            freshness=classify(
                manual.age_seconds,
                settings.freshness_fresh_seconds,
                settings.freshness_stale_seconds,
            ),
            is_manual=True,
            collected_value=value,
        )

    age = data_age_seconds(date, now)
    return PriceField(
        value=value,
        age_seconds=age,
        freshness=classify(
            age, settings.freshness_fresh_seconds, settings.freshness_stale_seconds
        ),
        manual_expired=manual is not None,
    )


def to_price_out(
    price: MarketPrice,
    item: Item,
    location: Location,
    now: datetime,
    settings: Settings,
    liquidity: LiquiditySignal | None = None,
    manual: ManualPriceOverlay | None = None,
) -> MarketPriceOut:
    observed_age = data_age_seconds(price.observed_at, now) or 0

    # Preço manual vence o coletado — nas duas pontas, e cada uma com a sua
    # chave. COMPRA é o que você paga (sell_min); VENDA é o que você recebe
    # (buy_max). Trocar as duas inverteria o sinal do lucro.
    compra = venda = None
    if manual is not None:
        compra = manual.quote(item.unique_name, location.slug, price.quality, KIND_BUY)
        venda = manual.quote(item.unique_name, location.slug, price.quality, KIND_SELL)

    # A distância até a mediana usa o preço que está em uso, manual inclusive:
    # comparar a mediana com um número que a tela não mostra confunde.
    sell_min_em_uso = (
        compra.price
        if compra is not None and compra.applies
        else price.sell_price_min
    )

    mediana = liquidity.median_price if liquidity else None
    # Compara com o preço que alguém paga comprando agora. Usar buy_max aqui
    # misturaria as duas pontas e daria uma distância que não existe.
    distancia = percentage_change(
        float(sell_min_em_uso) if sell_min_em_uso is not None else None, mediana
    )

    return MarketPriceOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name, price.quality),
        tier=item.tier,
        enchantment=item.enchantment,
        location=location.display_name,
        location_kind=location.kind,
        quality=price.quality,
        sell_min=_field(
            price.sell_price_min, price.sell_price_min_date, now, settings, compra
        ),
        sell_max=_field(price.sell_price_max, price.sell_price_max_date, now, settings),
        buy_min=_field(price.buy_price_min, price.buy_price_min_date, now, settings),
        buy_max=_field(
            price.buy_price_max, price.buy_price_max_date, now, settings, venda
        ),
        observed_age_seconds=observed_age,
        observed_freshness=classify(
            observed_age, settings.freshness_fresh_seconds, settings.freshness_stale_seconds
        ),
        liquidity=LiquidityOut(
            status="KNOWN" if liquidity and liquidity.known else "UNKNOWN",
            units_per_day=liquidity.units_per_day if liquidity else None,
            days_with_data=liquidity.days_with_data if liquidity else 0,
            period_days=liquidity.period_days if liquidity else 30,
        ),
        median_30d=round(mediana, 2) if mediana is not None else None,
        vs_median_pct=round(distancia, 1) if distancia is not None else None,
    )
