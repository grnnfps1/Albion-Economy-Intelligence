from pydantic import BaseModel, Field

from app.calculations.statistics import Trend


class HistoryPoint(BaseModel):
    timestamp: str
    avg_price: int
    item_count: int
    is_outlier: bool = Field(
        description="Ponto suspeito. Fica visível no gráfico; não entra nas médias."
    )


class HistorySeries(BaseModel):
    location: str
    location_slug: str
    quality: int
    points: list[HistoryPoint]

    minimum: int | None
    maximum: int | None
    average: float | None
    median: float | None = Field(
        description="Referência preferida: o AODP já entrega média por bucket, e "
        "média de médias contaminadas propaga outlier."
    )
    outlier_count: int
    change_pct: float | None
    trend: Trend


class HistoryResponse(BaseModel):
    server: str
    item: str
    item_name: str | None
    timescale: int
    period_days: int
    total_points: int
    series: list[HistorySeries]
    data_source: str = "Albion Online Data Project"
    data_source_note: str


class GoldPoint(BaseModel):
    timestamp: str
    price: int


class GoldResponse(BaseModel):
    server: str
    points: list[GoldPoint]
    current: int | None
    minimum: int | None
    maximum: int | None
    median: float | None
    change_pct: float | None
    trend: Trend
