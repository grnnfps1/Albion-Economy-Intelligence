"""Collector de preços de mercado.

Orquestra o caminho completo de uma coleta:

    catálogo rastreado → client AODP → normalização → market_prices
                                    ↘ raw_responses
                                    ↘ collector_runs

Cada etapa já existe isolada e testada; aqui só se amarra. O que este módulo
acrescenta de próprio é a **política**: quais itens varrer, em que ordem, o que
fazer quando o lote falha, e o que registrar.

Regras de operação:

- Um lock por servidor. Dois collectors do mesmo servidor não corrompem dado (o
  upsert resolve), mas dobram o consumo de rate limit, e o orçamento é de 1 req/s.
- Um lote que falha não derruba a coleta inteira. O erro é contado, registrado e
  a varredura segue -- perder 50 itens é melhor do que perder 300.
- Linha rejeitada é contada, nunca descartada em silêncio.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.locks import collector_lock
from app.collectors.aodp.client import AodpClient, AodpError
from app.collectors.aodp.normalization import (
    MarketPriceRecord,
    RejectedRow,
    normalize_price_row,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories import items as items_repo
from app.repositories import market as market_repo
from app.repositories import observability as obs_repo
from app.repositories import reference as reference_repo

log = get_logger(__name__)

COLLECTOR_NAME = "market"
ALL_QUALITIES = [1, 2, 3, 4, 5]


@dataclass
class CollectionResult:
    server_code: str
    items_requested: int = 0
    rows_received: int = 0
    rows_upserted: int = 0
    rows_rejected: int = 0
    http_requests: int = 0
    rate_limited: int = 0
    cache_hits: int = 0
    waited_seconds: float = 0.0
    failed_batches: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    status: str = "success"
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            key: value
            for key, value in self.__dict__.items()
            if key != "rejection_reasons" or value
        }


def _count_rejection(result: CollectionResult, rejected: RejectedRow) -> None:
    result.rows_rejected += 1
    result.rejection_reasons[rejected.reason] = (
        result.rejection_reasons.get(rejected.reason, 0) + 1
    )


async def _load_lookups(
    session: AsyncSession, server_code: str
) -> tuple[int, dict[str, int], dict[str, int], int]:
    """Carrega em memória o que a normalização precisa para resolver ids."""
    servers = await reference_repo.list_servers(session)
    server = next((row for row in servers if row.code == server_code), None)
    if server is None:
        raise ValueError(f"servidor não cadastrado no banco: {server_code}")

    locations = await reference_repo.list_locations(session)
    location_ids = {location.aodp_name: location.id for location in locations}

    source = await reference_repo.get_data_source(session, "aodp")
    if source is None:
        raise ValueError("fonte 'aodp' ausente. Rodou `alembic upgrade head`?")

    tracked, _ = await items_repo.search_items(session, tracked_only=True, limit=100_000)
    item_ids = {item.unique_name: item.id for item in tracked}

    return server.id, location_ids, item_ids, source.id


async def collect_market_prices(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    server_code: str,
    http_client: httpx.AsyncClient,
    locations: list[str] | None = None,
    qualities: list[int] | None = None,
    batch_size: int | None = None,
    store_raw: bool = True,
) -> CollectionResult:
    """Varre os itens marcados como `is_tracked` e atualiza `market_prices`."""
    result = CollectionResult(server_code=server_code)

    async with collector_lock(redis, f"{COLLECTOR_NAME}:{server_code}", ttl_seconds=1800):
        async with session_factory() as session:
            server_id, location_ids, item_ids, source_id = await _load_lookups(
                session, server_code
            )
            run = await obs_repo.start_run(session, COLLECTOR_NAME, server_id)
            await session.commit()
            run_id = run.id

        target_locations = locations or [name for name in location_ids]
        target_qualities = qualities or ALL_QUALITIES
        item_names = list(item_ids)
        result.items_requested = len(item_names)

        if not item_names:
            log.warning(
                "nenhum item marcado para coleta",
                server=server_code,
                hint="rode `python -m app.cli.import_items --apply-tracking`",
            )

        client = AodpClient(settings, server_code, http_client, redis=redis)
        observed_at = datetime.now(UTC)

        # O client já divide por comprimento de URL. `batch_size` só existe para
        # limitar quanto se segura em memória antes de gravar.
        chunk = batch_size or 200

        try:
            for start in range(0, len(item_names), chunk):
                names = item_names[start : start + chunk]
                try:
                    rows, captures = await client.fetch_prices(
                        names,
                        locations=target_locations,
                        qualities=target_qualities,
                        use_cache=False,  # coleta sempre busca o valor novo
                    )
                except AodpError as exc:
                    # Um lote ruim não pode custar a varredura inteira.
                    result.failed_batches += 1
                    result.status = "partial"
                    log.warning(
                        "lote falhou; seguindo",
                        server=server_code,
                        items=len(names),
                        error=str(exc),
                    )
                    continue

                result.rows_received += len(rows)

                records: list[MarketPriceRecord] = []
                for row in rows:
                    normalized = normalize_price_row(
                        row, server_id, location_ids, item_ids, source_id, observed_at
                    )
                    if isinstance(normalized, RejectedRow):
                        _count_rejection(result, normalized)
                        continue
                    records.append(normalized)

                async with session_factory() as session:
                    result.rows_upserted += await market_repo.upsert_prices(session, records)
                    if store_raw:
                        await obs_repo.save_raw_responses(
                            session, captures, source_id, server_id
                        )
                    await session.commit()

        except Exception as exc:  # noqa: BLE001 - a falha vira registro, não stacktrace perdido
            result.status = "failed"
            result.error_message = f"{type(exc).__name__}: {exc}"
            log.error("coleta falhou", server=server_code, error=result.error_message)

        result.http_requests = client.stats.http_requests
        result.rate_limited = client.stats.rate_limited
        result.cache_hits = client.stats.cache_hits
        result.waited_seconds = round(client.stats.waited_seconds, 2)

        if result.failed_batches and result.status == "success":
            result.status = "partial"

        async with session_factory() as session:
            run = await session.get(type(run), run_id)
            if run is not None:
                await obs_repo.finish_run(
                    session,
                    run,
                    status=result.status,
                    http_requests=result.http_requests,
                    rows_upserted=result.rows_upserted,
                    rows_rejected=result.rows_rejected,
                    rate_limited_count=result.rate_limited,
                    error_message=result.error_message,
                )
                await session.commit()

    log.info("coleta concluida", **result.as_dict())
    return result
