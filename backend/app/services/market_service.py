"""Montagem das respostas de mercado.

A idade do dado é calculada aqui, não no banco e não no frontend: o limiar de
frescor é configuração e pode mudar sem migration nem deploy do frontend.
"""

from datetime import datetime

from app.core.config import Settings
from app.core.freshness import classify, data_age_seconds
from app.models.catalog import Item
from app.models.market import MarketPrice
from app.models.reference import Location
from app.schemas.market import MarketPriceOut, PriceField

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
) -> MarketPriceOut:
    observed_age = data_age_seconds(price.observed_at, now) or 0
    return MarketPriceOut(
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
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
    )
