from pydantic import BaseModel, Field

from app.schemas.crafting import CraftParamsUsed


class FocusPlanOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    enchantment: int
    route: str = Field(description="CRAFTING ou REFINO")

    profit_per_unit: float
    focus_per_unit: float
    profit_per_focus: float | None

    units_by_focus: float | None = Field(description="Quanto o Focus disponível permite.")
    units_by_liquidity: float | None = Field(description="Quanto o mercado escoa no horizonte.")
    units: float | None
    focus_used: float | None
    realizable_profit: float | None = Field(
        description="Ganho dentro dos dois tetos. É o número que se realiza, "
        "diferente da taxa prata/Focus."
    )
    limiter: str
    days_to_sell: float | None
    liquidity_units_per_day: float | None


class FocusResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    focus_budget: float | None
    horizon_days: int
    sort_by: str
    total: int
    params: CraftParamsUsed
    generated_at: str
    data_source_note: str
    plans: list[FocusPlanOut]
