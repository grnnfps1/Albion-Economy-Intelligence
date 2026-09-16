from pydantic import BaseModel, Field

from app.schemas.arbitrage import FeesUsed
from app.schemas.risk import RiskOut, RiskUsed


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
    location: str | None = Field(default=None, description="Cidade onde esta compra acontece.")
    location_slug: str | None = None
    age_seconds: int | None

    # Quando a compra sai da cidade base, a resposta precisa dizer quanto o
    # desvio vale. Economia sem o número é só uma promessa.
    is_alternate_city: bool = False
    base_unit_price: int | None = Field(
        default=None, description="Preço na cidade base, para comparação."
    )
    savings_vs_base: float | None = Field(
        default=None,
        description="Economia desta linha contra a cidade base. None quando a base "
        "não tem cotação: aí não há o que comparar.",
    )


class SourcingOut(BaseModel):
    """O roteiro de compra: em quantas cidades ele cai e quanto isso rende.

    `cities_involved` é informação de primeira classe porque economia espalhada
    não é economia: 3% distribuídos por quatro cidades custam quatro viagens.
    """

    mode: str
    cities_involved: int
    cities: list[str] = Field(default_factory=list)

    cost_single_city: float | None = None
    cost_cheapest: float | None = None
    savings: float | None = None
    savings_pct: float | None = None

    # Só em COMPARAR: os dois roteiros calculados até o fim, não só o custo.
    profit_single_city: float | None = None
    profit_cheapest: float | None = None


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
    material_sourcing: SourcingOut
    risk: RiskOut
    economics: CraftEconomicsOut


class CraftingResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    crafts: int
    sort_by: str
    sourcing_mode: str = "CIDADE_UNICA"
    total: int
    params: CraftParamsUsed
    risk: RiskUsed
    generated_at: str
    data_source_note: str
    opportunities: list[CraftOpportunityOut]
