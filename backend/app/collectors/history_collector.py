"""Collector de histórico e de gold.

Duas diferenças em relação ao collector de preços:

1. **Frequência menor.** O histórico é agregado por hora ou por dia; recoletar
   de minuto em minuto gasta cota sem produzir informação nova.
2. **Marcação de outlier depois da gravação.** O valor cru entra primeiro; a
   marcação precisa da janela inteira à vista para decidir o que é pico e o que
   é a série normal.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.locks import collector_lock
from app.calculations.statistics import flag_outliers
from app.collectors.aodp.client import AodpClient, AodpError
from app.collectors.aodp.normalization import (
    RejectedRow,
    normalize_gold_point,
    normalize_history_series,
)
from app.collectors.market_collector import load_lookups
from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories import history as history_repo
from app.repositories import observability as obs_repo

log = get_logger(__name__)

HISTORY_COLLECTOR = "history"
GOLD_COLLECTOR = "gold"


@dataclass
class HistoryResult:
    server_code: str
    timescale: int
    items_requested: int = 0
    buckets_upserted: int = 0
    rows_rejected: int = 0
    outliers_marked: int = 0
    http_requests: int = 0
    failed_batches: int = 0
    status: str = "success"
    error_message: str | None = None
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


async def _mark_window(
    session: AsyncSession,
    server_code: str,
    item_names: list[str],
    timescale: int,
    since: datetime,
) -> int:
    """Recalcula `is_outlier` por (item, local, qualidade) dentro da janela.

    A marcação é sempre por série completa, nunca por ponto isolado: um preço só
    é suspeito em relação aos vizinhos.
    """
    marked = 0
    for unique_name in item_names:
        rows = await history_repo.load_series(
            session, server_code, unique_name, timescale=timescale, since=since
        )
        grupos: dict[tuple, list] = {}
        for record, location in rows:
            grupos.setdefault((location.slug, record.quality), []).append(record)

        marks: dict[tuple, bool] = {}
        for records in grupos.values():
            records.sort(key=lambda row: row.bucket_ts)
            flags = flag_outliers([float(row.avg_price) for row in records])
            for record, is_outlier in zip(records, flags, strict=True):
                marks[
                    (
                        record.server_id,
                        record.location_id,
                        record.item_id,
                        record.quality,
                        record.timescale,
                        record.bucket_ts,
                    )
                ] = is_outlier

        marked += await history_repo.mark_outliers(session, marks)
    return marked


async def collect_history(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    server_code: str,
    http_client: httpx.AsyncClient,
    timescale: int = 24,
    days: int = 30,
    batch_size: int = 50,
) -> HistoryResult:
    result = HistoryResult(server_code=server_code, timescale=timescale)
    since = datetime.now(UTC) - timedelta(days=days)

    async with collector_lock(
        redis, f"{HISTORY_COLLECTOR}:{server_code}:{timescale}", ttl_seconds=3600
    ):
        async with session_factory() as session:
            server_id, location_ids, item_ids, source_id = await load_lookups(
                session, server_code
            )
            run = await obs_repo.start_run(session, HISTORY_COLLECTOR, server_id)
            await session.commit()
            run_id = run.id

        item_names = list(item_ids)
        result.items_requested = len(item_names)
        client = AodpClient(settings, server_code, http_client, redis=redis)
        ingested_at = datetime.now(UTC)

        try:
            for start in range(0, len(item_names), batch_size):
                names = item_names[start : start + batch_size]
                try:
                    series, captures = await client.fetch_history(
                        names,
                        timescale=timescale,
                        locations=list(location_ids),
                        date=since.strftime("%Y-%m-%d"),
                        use_cache=False,
                    )
                except AodpError as exc:
                    result.failed_batches += 1
                    result.status = "partial"
                    log.warning("lote de historico falhou", items=len(names), error=str(exc))
                    continue

                records = []
                for entry in series:
                    parsed, rejected = normalize_history_series(
                        entry, server_id, timescale, location_ids, item_ids,
                        source_id, ingested_at,
                    )
                    records.extend(parsed)
                    for row in rejected:
                        result.rows_rejected += 1
                        result.rejection_reasons[row.reason] = (
                            result.rejection_reasons.get(row.reason, 0) + 1
                        )

                async with session_factory() as session:
                    result.buckets_upserted += await history_repo.upsert_history(
                        session, records
                    )
                    await obs_repo.save_raw_responses(session, captures, source_id, server_id)
                    await session.commit()

                # Marcação depois da gravação: precisa da janela inteira.
                async with session_factory() as session:
                    result.outliers_marked += await _mark_window(
                        session, server_code, names, timescale, since
                    )
                    await session.commit()

        except Exception as exc:  # noqa: BLE001
            result.status = "failed"
            result.error_message = f"{type(exc).__name__}: {exc}"
            log.error("coleta de historico falhou", error=result.error_message)

        result.http_requests = client.stats.http_requests
        if result.failed_batches and result.status == "success":
            result.status = "partial"

        async with session_factory() as session:
            run = await session.get(type(run), run_id)
            if run is not None:
                await obs_repo.finish_run(
                    session, run, status=result.status,
                    http_requests=result.http_requests,
                    rows_upserted=result.buckets_upserted,
                    rows_rejected=result.rows_rejected,
                    rate_limited_count=client.stats.rate_limited,
                    error_message=result.error_message,
                )
                await session.commit()

    log.info("historico coletado", **result.as_dict())
    return result


async def collect_gold(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    server_code: str,
    http_client: httpx.AsyncClient,
    count: int = 100,
) -> int:
    """Cotação de gold. O endpoint não informa servidor -- ele vem do host."""
    async with collector_lock(redis, f"{GOLD_COLLECTOR}:{server_code}", ttl_seconds=600):
        async with session_factory() as session:
            server_id, _locations, _items, source_id = await load_lookups(session, server_code)

        client = AodpClient(settings, server_code, http_client, redis=redis)
        points, captures = await client.fetch_gold(count=count, use_cache=False)

        records = []
        for point in points:
            normalized = normalize_gold_point(point, server_id, source_id)
            if isinstance(normalized, RejectedRow):
                continue
            records.append(normalized)

        async with session_factory() as session:
            saved = await history_repo.upsert_gold(session, records)
            raw = [captures] if captures is not None else []
            await obs_repo.save_raw_responses(session, raw, source_id, server_id)
            await session.commit()

    log.info("gold coletado", server=server_code, pontos=saved)
    return saved
