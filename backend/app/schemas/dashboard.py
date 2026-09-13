from pydantic import BaseModel, Field

from app.core.freshness import Freshness
from app.schemas.crafting import CraftParamsUsed


class PipelineHealth(BaseModel):
    """Estado da coleta.

    Vem antes dos números de propósito. Se o collector parou, todos os cards
    abaixo estão olhando um retrato antigo, e o usuário precisa saber disso
    antes de tomar decisão — não depois.
    """

    prices_tracked: int
    last_collection_age_seconds: int | None
    freshness: Freshness
    last_run_status: str | None = None
    stale_price_ratio: float | None = Field(
        default=None,
        description="Fração dos preços mais velhos que o limite de frescor.",
    )


class DashboardCard(BaseModel):
    """Uma oportunidade, com o contexto que a torna confiável.

    `headline` sozinho seria vitrine. Idade e confiança vão junto porque é o que
    separa uma recomendação de um número grande.
    """

    kind: str = Field(description="ARBITRAGEM | CRAFTING | REFINO | FOCUS")
    available: bool
    reason: str | None = None

    item: str | None = None
    item_name: str | None = None
    icon_url: str | None = None
    tier: int | None = None

    headline: float | None = None
    headline_label: str | None = None
    detail: str | None = None

    age_seconds: int | None = None
    freshness: Freshness = Freshness.UNKNOWN
    score: int | None = None
    confidence: float | None = None
    liquidity_units_per_day: float | None = None
    href: str


class DashboardResponse(BaseModel):
    server: str
    generated_at: str
    pipeline: PipelineHealth
    params: CraftParamsUsed
    cards: list[DashboardCard]
    top_opportunities: list[DashboardCard]
    data_source_note: str
