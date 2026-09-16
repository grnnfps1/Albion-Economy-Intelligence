from pydantic import BaseModel, Field

from app.schemas.catalog import CategoryOut  # noqa: F401  (mantém o módulo coeso)
from app.schemas.risk import RiskOut, RiskUsed


class FeesUsed(BaseModel):
    """As taxas que produziram estes números.

    Vai na resposta de propósito: sem isso, um lucro de 18% não é auditável. O
    usuário precisa poder conferir com que imposto o número foi calculado.
    """

    setup_fee_pct: float | None = None
    sales_tax_pct: float | None = None
    premium: bool | None = None
    source: str = Field(
        default="UNKNOWN",
        description="'usuario' quando veio da requisição, 'config' quando veio do banco.",
    )
    complete: bool = False
    missing: list[str] = Field(default_factory=list)


class EconomicsOut(BaseModel):
    known: bool
    reason: str | None = None
    quantity: int
    unit_cost: float | None = None
    investment: float | None = None
    gross_revenue: float | None = None
    fees: float | None = None
    transport_cost: float | None = None
    net_profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None


class ScoreOut(BaseModel):
    value: int | None = None
    band: str = "desconhecida"
    confidence: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)


class OpportunityOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    enchantment: int
    quality: int
    strategy: str
    origin: str
    origin_slug: str
    destination: str
    destination_slug: str
    buy_price: int
    sell_price: int
    spread_pct: float
    worst_age_seconds: int
    liquidity_units_per_day: float | None
    economics: EconomicsOut
    risk: RiskOut
    score: ScoreOut


class ArbitrageResponse(BaseModel):
    server: str
    strategy: str
    quantity: int
    total: int
    fees: FeesUsed
    risk: RiskUsed
    generated_at: str
    data_source_note: str
    opportunities: list[OpportunityOut]
