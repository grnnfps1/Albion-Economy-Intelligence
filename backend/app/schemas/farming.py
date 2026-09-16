from pydantic import BaseModel, Field

from app.schemas.arbitrage import FeesUsed
from app.schemas.crafting import SourcingOut


class FarmingParamsUsed(BaseModel):
    """Os parâmetros e as leituras do dump que produziram estes números.

    `assumptions` existe porque nem tudo em `farmableitem` é inequívoco. O que
    foi lido literalmente do dump e o que foi interpretado precisam estar
    separados na resposta, ou um número plausível passa por medido.
    """

    fees: FeesUsed = Field(default_factory=FeesUsed)
    complete: bool = False
    missing: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class FarmInputOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    role: str = Field(description="semente, filhote ou ração")
    quantity: float
    unit_price: int | None
    total_price: float | None
    location: str | None = None
    location_slug: str | None = None
    age_seconds: int | None = None
    is_alternate_city: bool = False
    savings_vs_base: float | None = None


class FarmOutputOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    role: str
    amount_min: int
    amount_max: int
    chance: float
    expected_amount: float
    unit_price: int | None
    primary: bool


class FarmEconomicsOut(BaseModel):
    known: bool
    reason: str | None = None
    kind: str

    cycle_seconds: int
    cycle_days: float
    focus_cost: int

    input_cost: float | None = None
    gross_revenue: float | None = None
    sale_revenue_net: float | None = None
    market_fees: float | None = None

    profit_per_cycle: float | None = None
    # As duas medidas que põem cenoura e barra de aço na mesma régua.
    profit_per_day: float | None = None
    profit_per_focus: float | None = None
    focus_per_day: float | None = None

    margin_pct: float | None = None
    roi_pct: float | None = None
    outputs_without_price: list[str] = Field(default_factory=list)


class FarmPlanOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    station: str = Field(description="farm | herbgarden | pasture | kennel")
    station_label: str
    kind: str = Field(description="CULTIVO | CRIACAO | PRODUTO")

    buy_location: str
    sell_location: str
    focus_cycles: int | None = None
    liquidity_units_per_day: float | None = None
    # O comerciante de fazenda vende semente e filhote por prata fixa. O cálculo
    # usa o preço de mercado; este número vai junto para a comparação existir,
    # em vez de ficar escondida numa escolha do motor.
    npc_silver_cost: int | None = None

    inputs: list[FarmInputOut]
    outputs: list[FarmOutputOut]
    material_sourcing: SourcingOut
    economics: FarmEconomicsOut


class FarmingResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    sort_by: str
    sourcing_mode: str = "CIDADE_UNICA"
    total: int
    params: FarmingParamsUsed
    generated_at: str
    data_source_note: str
    stations: list[str] = Field(default_factory=list)
    plans: list[FarmPlanOut]
