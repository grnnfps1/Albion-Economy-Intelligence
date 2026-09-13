from typing import Literal

from pydantic import BaseModel, Field

from app.core.freshness import Freshness


class PriceField(BaseModel):
    """Um preço e a idade dele.

    `value` nulo significa que não existe ordem -- e é diferente de zero
    (requisito 52). `age_seconds` nulo acompanha: sem cotação, não há idade.
    """

    value: int | None = None
    age_seconds: int | None = None
    freshness: Freshness = Freshness.UNKNOWN


class LiquidityOut(BaseModel):
    """Sinal de giro, derivado do histórico.

    `status = UNKNOWN` é resposta legítima: sem histórico suficiente, não se
    inventa liquidez (requisito 21). Margem enorme em item que ninguém compra
    vale menos que margem pequena em item líquido.
    """

    status: Literal["KNOWN", "UNKNOWN"] = "UNKNOWN"
    units_per_day: float | None = None
    days_with_data: int = 0
    period_days: int = 30


class MarketPriceOut(BaseModel):
    item: str = Field(description="Id técnico do Albion.")
    item_name: str | None
    tier: int | None
    enchantment: int
    location: str
    location_kind: str
    quality: int

    # Buy e sell são independentes: quem compra do mercado paga sell_min,
    # quem vende na hora recebe buy_max (requisito 13).
    sell_min: PriceField
    sell_max: PriceField
    buy_min: PriceField
    buy_max: PriceField

    observed_age_seconds: int
    observed_freshness: Freshness

    liquidity: LiquidityOut = Field(default_factory=LiquidityOut)
    median_30d: float | None = Field(
        default=None,
        description="Mediana do período, excluindo outliers. Referência para "
        "julgar se o preço atual está caro ou barato.",
    )
    vs_median_pct: float | None = Field(
        default=None, description="Distância do preço de venda mínimo até a mediana."
    )


class MarketPricePage(BaseModel):
    server: str
    total: int
    limit: int
    offset: int
    sort_by: str
    descending: bool
    generated_at: str
    data_source: str = "Albion Online Data Project"
    data_source_note: str
    prices: list[MarketPriceOut]
