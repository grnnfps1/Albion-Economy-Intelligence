from pydantic import BaseModel, Field

from app.schemas.arbitrage import FeesUsed


class CraftParamsUsed(BaseModel):
    """Os parâmetros que produziram estes números.

    Vão na resposta porque nenhum deles é fato fixo: retorno muda com Focus e
    especialização, taxa de estação muda por cidade e por hora, imposto muda com
    Premium. Sem isso, um lucro de 18% não é auditável.
    """

    return_rate: float | None = None
    station_fee: float | None = None
    fees: FeesUsed = Field(default_factory=FeesUsed)
    complete: bool = False
    missing: list[str] = Field(default_factory=list)


class MaterialOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    quantity: int
    unit_price: int | None
    total_price: float | None
    is_returnable: bool
    location: str | None
    age_seconds: int | None


class CraftEconomicsOut(BaseModel):
    known: bool
    reason: str | None = None
    output_quantity: int
    focus_cost: int
    material_cost_gross: float | None = None
    material_cost_net: float | None = None
    returned_value: float | None = None
    station_fee: float | None = None
    sale_revenue_net: float | None = None
    market_fees: float | None = None
    profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None
    profit_per_focus: float | None = None


class CraftOpportunityOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    enchantment: int
    recipe_variant: int
    station_category: str | None
    buy_location: str
    sell_location: str
    sell_price: int | None
    sell_age_seconds: int | None
    liquidity_units_per_day: float | None
    materials: list[MaterialOut]
    economics: CraftEconomicsOut


class CraftingResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    crafts: int
    sort_by: str
    total: int
    params: CraftParamsUsed
    generated_at: str
    data_source_note: str
    opportunities: list[CraftOpportunityOut]
