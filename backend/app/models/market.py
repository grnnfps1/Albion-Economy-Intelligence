"""Preços, histórico e gold."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketPrice(Base):
    """Snapshot atual por (servidor, local, item, qualidade).

    Buy e sell são guardados separadamente (requisito 13): quem compra do mercado
    paga `sell_price_min`; quem vende na hora recebe `buy_price_max`. Trocar os
    dois inverte o sinal do lucro.

    Todos os preços são NULL quando não há ordem. O AODP devolve 0 com data
    0001-01-01 nesse caso, e a normalização converte -- zero e ausência são
    coisas diferentes (requisito 52).

    Cada campo de preço tem a sua própria data: `sell_price_min_date` pode ser de
    agora e `buy_price_max_date` de três dias atrás na mesma linha.
    """

    __tablename__ = "market_prices"
    __table_args__ = (
        CheckConstraint("quality BETWEEN 1 AND 5", name="ck_market_prices_quality"),
        CheckConstraint(
            "(sell_price_min IS NULL OR sell_price_min > 0) "
            "AND (sell_price_max IS NULL OR sell_price_max > 0) "
            "AND (buy_price_min IS NULL OR buy_price_min > 0) "
            "AND (buy_price_max IS NULL OR buy_price_max > 0)",
            name="ck_market_prices_no_zero_sentinel",
        ),
        Index("ix_market_prices_server_item", "server_id", "item_id"),
        Index("ix_market_prices_observed", "server_id", "observed_at"),
    )

    server_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    quality: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    sell_price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sell_price_min_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sell_price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sell_price_max_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    buy_price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    buy_price_min_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    buy_price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    buy_price_max_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Quando o collector buscou. Diferente da data da ordem: mede o frescor da
    # coleta, não o da cotação.
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )


class MarketHistory(Base):
    """Bucket agregado do endpoint de histórico do AODP.

    Atenção: o AODP agrega **somente sell orders** e devolve média, não mediana.
    Média é sensível a ordem manipulada -- ver docs/02-aodp.md. Por isso o valor
    cru é guardado e `is_outlier` marca o que a normalização considerou suspeito;
    nada é apagado.
    """

    __tablename__ = "market_history"
    __table_args__ = (
        CheckConstraint("quality BETWEEN 1 AND 5", name="ck_market_history_quality"),
        CheckConstraint("timescale IN (1, 6, 24)", name="ck_market_history_timescale"),
        CheckConstraint("item_count >= 0", name="ck_market_history_item_count"),
        Index("ix_market_history_lookup", "server_id", "item_id", "timescale", "bucket_ts"),
    )

    server_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    quality: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    timescale: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GoldPrice(Base):
    """Cotação de gold em prata.

    O endpoint do AODP não devolve servidor -- o servidor é o host chamado. Por
    isso `server_id` vem do collector, nunca do payload (docs/02-aodp.md).
    """

    __tablename__ = "gold_prices"
    __table_args__ = (CheckConstraint("price > 0", name="ck_gold_prices_price"),)

    server_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
