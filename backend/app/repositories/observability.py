"""Registro de execução dos collectors e dos payloads brutos."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.aodp.client import RawCapture
from app.models.observability import CollectorRun, RawResponse


async def start_run(session: AsyncSession, collector: str, server_id: int | None) -> CollectorRun:
    run = CollectorRun(
        collector=collector,
        server_id=server_id,
        started_at=datetime.now(UTC),
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def finish_run(
    session: AsyncSession,
    run: CollectorRun,
    status: str,
    http_requests: int = 0,
    rows_upserted: int = 0,
    rows_rejected: int = 0,
    rate_limited_count: int = 0,
    error_message: str | None = None,
) -> None:
    run.finished_at = datetime.now(UTC)
    run.status = status
    run.http_requests = http_requests
    run.rows_upserted = rows_upserted
    run.rows_rejected = rows_rejected
    run.rate_limited_count = rate_limited_count
    # Mensagem longa demais polui a tabela; o detalhe fica no log estruturado.
    run.error_message = error_message[:2000] if error_message else None
    await session.flush()


async def save_raw_responses(
    session: AsyncSession, captures: list[RawCapture], source_id: int, server_id: int
) -> int:
    """Guarda o payload cru para auditar uma normalização errada depois do fato."""
    if not captures:
        return 0
    session.add_all(
        [
            RawResponse(
                source_id=source_id,
                server_id=server_id,
                endpoint=capture.endpoint,
                request_url=capture.request_url,
                http_status=capture.http_status,
                fetched_at=capture.fetched_at,
                payload=capture.payload,
                payload_sha256=capture.payload_sha256,
            )
            for capture in captures
        ]
    )
    await session.flush()
    return len(captures)


async def purge_raw_responses(session: AsyncSession, older_than: datetime) -> int:
    """Retenção curta: isto cresce rápido e só serve para diagnóstico recente."""
    result = await session.execute(
        delete(RawResponse).where(RawResponse.fetched_at < older_than)
    )
    return result.rowcount or 0


async def last_run(session: AsyncSession, collector: str) -> CollectorRun | None:
    return await session.scalar(
        select(CollectorRun)
        .where(CollectorRun.collector == collector)
        .order_by(CollectorRun.started_at.desc())
        .limit(1)
    )
