"""Normalização das respostas do AODP.

Funções puras: entram objetos validados, saem registros prontos para o banco.
Sem I/O e sem relógio implícito -- o `observed_at` é sempre passado por quem
chama, o que torna o resultado reproduzível.

A regra que não pode ser quebrada: **ausência de dado vira None, nunca 0**
(requisito 52). O AODP sinaliza "não há ordem" com preço `0` e data
`0001-01-01T00:00:00`. Tratar isso como preço zero produz margem infinita e a
plataforma anuncia uma oportunidade que não existe.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.collectors.aodp.schemas import AodpGoldPoint, AodpHistorySeries, AodpPriceRow

# Data que o AODP usa para dizer "nunca houve ordem".
SENTINEL_YEAR = 1


@dataclass(frozen=True)
class RejectedRow:
    """Linha descartada, com o motivo. Descartar em silêncio esconde bug."""

    reason: str
    detail: str


@dataclass(frozen=True)
class MarketPriceRecord:
    server_id: int
    location_id: int
    item_id: int
    quality: int
    sell_price_min: int | None
    sell_price_min_date: datetime | None
    sell_price_max: int | None
    sell_price_max_date: datetime | None
    buy_price_min: int | None
    buy_price_min_date: datetime | None
    buy_price_max: int | None
    buy_price_max_date: datetime | None
    observed_at: datetime
    source_id: int

    @property
    def has_any_price(self) -> bool:
        return any(
            value is not None
            for value in (
                self.sell_price_min,
                self.sell_price_max,
                self.buy_price_min,
                self.buy_price_max,
            )
        )


@dataclass(frozen=True)
class MarketHistoryRecord:
    server_id: int
    location_id: int
    item_id: int
    quality: int
    timescale: int
    bucket_ts: datetime
    item_count: int
    avg_price: int
    source_id: int
    ingested_at: datetime


@dataclass(frozen=True)
class GoldPriceRecord:
    server_id: int
    ts: datetime
    price: int
    source_id: int


def to_utc(value: datetime) -> datetime:
    """Anexa UTC a timestamp sem fuso.

    O AODP devolve `2026-09-10T00:30:00`, sem fuso, e o valor é UTC. Deixar o
    driver adivinhar o fuso do servidor é bug silencioso: o preço vira 3 horas
    mais novo ou mais velho do que é.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def is_sentinel_date(value: datetime) -> bool:
    return value.year <= SENTINEL_YEAR


def normalize_price(value: int, date: datetime) -> tuple[int | None, datetime | None]:
    """Converte um par preço/data do AODP.

    Devolve (None, None) quando não há ordem. Preço positivo com data sentinela
    também é descartado: sem saber quando a cotação foi vista, ela não serve para
    decidir nada.
    """
    if value <= 0 or is_sentinel_date(date):
        return None, None
    return value, to_utc(date)


def normalize_price_row(
    row: AodpPriceRow,
    server_id: int,
    location_ids: dict[str, int],
    item_ids: dict[str, int],
    source_id: int,
    observed_at: datetime,
) -> MarketPriceRecord | RejectedRow:
    location_id = location_ids.get(row.city)
    if location_id is None:
        # Local novo no jogo, ou uma portal city que ainda não foi cadastrada.
        # Rejeitar e registrar é melhor do que criar uma linha órfã.
        return RejectedRow("local desconhecido", row.city)

    item_id = item_ids.get(row.item_id)
    if item_id is None:
        return RejectedRow("item fora do catálogo", row.item_id)

    if not 1 <= row.quality <= 5:
        return RejectedRow("qualidade fora da faixa", f"{row.item_id} q={row.quality}")

    sell_min, sell_min_date = normalize_price(row.sell_price_min, row.sell_price_min_date)
    sell_max, sell_max_date = normalize_price(row.sell_price_max, row.sell_price_max_date)
    buy_min, buy_min_date = normalize_price(row.buy_price_min, row.buy_price_min_date)
    buy_max, buy_max_date = normalize_price(row.buy_price_max, row.buy_price_max_date)

    return MarketPriceRecord(
        server_id=server_id,
        location_id=location_id,
        item_id=item_id,
        quality=row.quality,
        sell_price_min=sell_min,
        sell_price_min_date=sell_min_date,
        sell_price_max=sell_max,
        sell_price_max_date=sell_max_date,
        buy_price_min=buy_min,
        buy_price_min_date=buy_min_date,
        buy_price_max=buy_max,
        buy_price_max_date=buy_max_date,
        observed_at=observed_at,
        source_id=source_id,
    )


def normalize_history_series(
    series: AodpHistorySeries,
    server_id: int,
    timescale: int,
    location_ids: dict[str, int],
    item_ids: dict[str, int],
    source_id: int,
    ingested_at: datetime,
) -> tuple[list[MarketHistoryRecord], list[RejectedRow]]:
    location_id = location_ids.get(series.location)
    if location_id is None:
        return [], [RejectedRow("local desconhecido", series.location)]

    item_id = item_ids.get(series.item_id)
    if item_id is None:
        return [], [RejectedRow("item fora do catálogo", series.item_id)]

    if not 1 <= series.quality <= 5:
        return [], [RejectedRow("qualidade fora da faixa", f"{series.item_id} q={series.quality}")]

    records: list[MarketHistoryRecord] = []
    rejected: list[RejectedRow] = []

    for point in series.data:
        if point.avg_price <= 0:
            rejected.append(
                RejectedRow("preço não positivo", f"{series.item_id} @ {point.timestamp}")
            )
            continue
        if is_sentinel_date(point.timestamp):
            rejected.append(RejectedRow("data sentinela", series.item_id))
            continue
        records.append(
            MarketHistoryRecord(
                server_id=server_id,
                location_id=location_id,
                item_id=item_id,
                quality=series.quality,
                timescale=timescale,
                bucket_ts=to_utc(point.timestamp),
                item_count=max(0, point.item_count),
                avg_price=point.avg_price,
                source_id=source_id,
                ingested_at=ingested_at,
            )
        )

    return records, rejected


def normalize_gold_point(
    point: AodpGoldPoint, server_id: int, source_id: int
) -> GoldPriceRecord | RejectedRow:
    if point.price <= 0:
        return RejectedRow("preço não positivo", str(point.price))
    if is_sentinel_date(point.timestamp):
        return RejectedRow("data sentinela", str(point.timestamp))
    return GoldPriceRecord(
        server_id=server_id,
        ts=to_utc(point.timestamp),
        price=point.price,
        source_id=source_id,
    )
