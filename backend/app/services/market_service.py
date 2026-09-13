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
from app.models.market import MarketPrice
from app.models.reference import Location
from app.repositories.liquidity import LiquiditySignal
from app.schemas.market import LiquidityOut, MarketPriceOut, PriceField

DATA_SOURCE_NOTE = (
    "Preços vêm da coleta comunitária do Albion Online Data Project: dependem de "
    "jogadores terem aberto o mercado no jogo. Sem dado não significa preço baixo."
)


def _field(
    value: int | None, date: datetime | None, now: datetime, settings: Settings
) -> PriceField:
    age = data_age_seconds(date, now)
    return PriceField(
        value=value,
        age_seconds=age,
        freshness=classify(
            age, settings.freshness_fresh_seconds, settings.freshness_stale_seconds
        ),
    )


def to_price_out(
    price: MarketPrice,
    item: Item,
    location: Location,
    now: datetime,
    settings: Settings,
    liquidity: LiquiditySignal | None = None,
) -> MarketPriceOut:
    observed_age = data_age_seconds(price.observed_at, now) or 0

    mediana = liquidity.median_price if liquidity else None
    # Compara com o preço que alguém paga comprando agora. Usar buy_max aqui
    # misturaria as duas pontas e daria uma distância que não existe.
    distancia = percentage_change(
        float(price.sell_price_min) if price.sell_price_min is not None else None, mediana
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
        sell_min=_field(price.sell_price_min, price.sell_price_min_date, now, settings),
        sell_max=_field(price.sell_price_max, price.sell_price_max_date, now, settings),
        buy_min=_field(price.buy_price_min, price.buy_price_min_date, now, settings),
        buy_max=_field(price.buy_price_max, price.buy_price_max_date, now, settings),
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
