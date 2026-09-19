from pydantic import BaseModel, Field

from app.schemas.crafting import CraftParamsUsed, ReturnOut, SourcingOut


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

    # Só nos elos comprados: elo produzido não exige viagem nenhuma.
    location: str | None = None
    location_slug: str | None = None
    is_alternate_city: bool = False
    base_unit_price: int | None = None
    savings_vs_base: float | None = None

    # Qual variante da receita o motor usou, e qual ele descartou. Com token de
    # facção o custo muda bastante, e quem tem token parado no inventário
    # precisa saber que a rota existe mesmo quando não foi a escolhida.
    variant_label: str | None = None
    alternative_cost: float | None = None
    alternative_label: str | None = None


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
    material_sourcing: SourcingOut
    material_return: ReturnOut

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
    profit_per_day: float | None = None
    units_per_day: float | None = None
    daily_limiter: str = "DESCONHECIDO"
    daily_reason: str | None = None


class RefiningResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    sourcing: str
    sourcing_mode: str = "CIDADE_UNICA"
    total: int
    params: CraftParamsUsed
    generated_at: str
    data_source_note: str
    families: list[str]
    opportunities: list[RefiningOut]
