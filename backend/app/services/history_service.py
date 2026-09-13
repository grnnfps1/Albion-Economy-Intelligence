"""Montagem das respostas de histórico."""

from app.calculations.statistics import (
    Trend,
    classify_trend,
    percentage_change,
    summarize,
)
from app.models.market import GoldPrice, MarketHistory
from app.models.reference import Location
from app.schemas.history import GoldPoint, GoldResponse, HistoryPoint, HistorySeries

DATA_SOURCE_NOTE = (
    "O histórico do AODP cobre apenas ordens de venda e é agregado por média. "
    "Pontos marcados como outlier continuam visíveis, mas ficam fora das "
    "estatísticas do período."
)


def build_series(rows: list[tuple[MarketHistory, Location]]) -> list[HistorySeries]:
    grupos: dict[tuple[str, int], tuple[Location, list[MarketHistory]]] = {}
    for record, location in rows:
        key = (location.slug, record.quality)
        grupos.setdefault(key, (location, []))[1].append(record)

    series: list[HistorySeries] = []
    for location, records in grupos.values():
        records.sort(key=lambda row: row.bucket_ts)
        values = [float(row.avg_price) for row in records]
        marks = [row.is_outlier for row in records]
        summary = summarize(values, marks)

        # Variação compara os extremos limpos da janela: usar o último ponto
        # cru deixaria um outlier no fim virar "alta de 700%".
        limpos = [value for value, mark in zip(values, marks, strict=True) if not mark]
        change = percentage_change(limpos[-1], limpos[0]) if len(limpos) >= 2 else None
        trend = (
            classify_trend(limpos[-1], limpos[0]) if len(limpos) >= 2 else Trend.UNKNOWN
        )

        series.append(
            HistorySeries(
                location=location.display_name,
                location_slug=location.slug,
                quality=records[0].quality,
                points=[
                    HistoryPoint(
                        timestamp=row.bucket_ts.isoformat(),
                        avg_price=row.avg_price,
                        item_count=row.item_count,
                        is_outlier=row.is_outlier,
                    )
                    for row in records
                ],
                minimum=int(summary.minimum) if summary.minimum is not None else None,
                maximum=int(summary.maximum) if summary.maximum is not None else None,
                average=round(summary.average, 2) if summary.average is not None else None,
                median=summary.median_value,
                outlier_count=summary.outlier_count,
                change_pct=round(change, 2) if change is not None else None,
                trend=trend,
            )
        )

    series.sort(key=lambda item: item.location_slug)
    return series


def build_gold(server_code: str, rows: list[GoldPrice]) -> GoldResponse:
    values = [float(row.price) for row in rows]
    summary = summarize(values)
    change = percentage_change(values[-1], values[0]) if len(values) >= 2 else None

    return GoldResponse(
        server=server_code,
        points=[GoldPoint(timestamp=row.ts.isoformat(), price=row.price) for row in rows],
        current=rows[-1].price if rows else None,
        minimum=int(summary.minimum) if summary.minimum is not None else None,
        maximum=int(summary.maximum) if summary.maximum is not None else None,
        median=summary.median_value,
        change_pct=round(change, 2) if change is not None else None,
        trend=classify_trend(values[-1], values[0]) if len(values) >= 2 else Trend.UNKNOWN,
    )
