"""Rastro de execução dos collectors e payloads brutos (requisitos 17 e 40)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

COLLECTOR_STATUSES = ("running", "success", "partial", "failed")


class CollectorRun(Base):
    __tablename__ = "collector_runs"
    __table_args__ = (
        CheckConstraint("status IN " + str(COLLECTOR_STATUSES), name="ck_collector_runs_status"),
        Index("ix_collector_runs_recent", "collector", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collector: Mapped[str] = mapped_column(String(64), nullable=False)
    server_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")

    http_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limited_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawResponse(Base):
    """Payload cru, para auditar uma normalização errada depois do fato.

    Retenção curta e configurável -- isto cresce rápido.
    """

    __tablename__ = "raw_responses"
    __table_args__ = (Index("ix_raw_responses_fetched", "fetched_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    server_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True
    )
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
