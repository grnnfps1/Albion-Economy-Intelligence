from pydantic import BaseModel, Field

from app.schemas.crafting import CraftParamsUsed


class ChainStepOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    sourcing: str = Field(description="MERCADO ou PRODUZIR")
    unit_cost: float | None
    market_price: int | None
    craft_cost: float | None = Field(
        default=None, description="Custo de produzir esta unidade, quando há receita."
    )
    depth: int


class RefiningOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    enchantment: int
    family: str | None = Field(description="Raiz do item: PLANKS, METALBAR, LEATHER…")
    station_category: str | None

    sell_price: int | None
    sell_age_seconds: int | None
    liquidity_units_per_day: float | None

    sourcing: str
    unit_cost: float | None
    focus_per_unit: float
    chain: list[ChainStepOut]

    # Comparação explícita: as duas respostas são certas, para pessoas
    # diferentes. Quem compra tudo pronto olha a primeira; quem já tem a cadeia
    # montada olha a segunda.
    cost_from_market: float | None = None
    cost_from_crafting: float | None = None

    known: bool
    reason: str | None = None
    profit: float | None = None
    margin_pct: float | None = None
    profit_per_focus: float | None = None


class RefiningResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    sourcing: str
    total: int
    params: CraftParamsUsed
    generated_at: str
    data_source_note: str
    families: list[str]
    opportunities: list[RefiningOut]
