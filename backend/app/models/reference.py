"""Tabelas de referência: servidores, locais, categorias e fontes de dado."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

LOCATION_KINDS = ("royal_city", "black_market", "portal_city", "rest_zone", "other")


class Server(Base, TimestampMixin):
    """Servidor de jogo. Dado de mercado nunca cruza servidores (requisito 5)."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    aodp_base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Location(Base, TimestampMixin):
    """Local de mercado.

    Black Market fica aqui, mas marcado com kind='black_market': não é cidade
    (requisito 31) e a semântica de ordem é diferente. Manter na mesma tabela
    evita dois caminhos de código para a mesma consulta; o `kind` carrega a
    diferença.
    """

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint(
            "kind IN " + str(LOCATION_KINDS),
            name="ck_locations_kind",
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    # String exata devolvida pelo AODP, incluindo espaços: "Fort Sterling", "Black Market".
    aodp_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    supports_buy_orders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ItemCategory(Base, TimestampMixin):
    """Categoria do item, hierárquica.

    Os códigos vêm de `@shopcategory` / `@shopsubcategory1` do dump oficial --
    não são inventados aqui.
    """

    __tablename__ = "item_categories"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    # Único: os códigos vêm de `@shopcategory`, que é um espaço plano no dump.
    # A auto-referência existe para hierarquia futura, não para repetir código.
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(96), nullable=False)

    parent: Mapped["ItemCategory | None"] = relationship(remote_side=[id])

    __table_args__ = (
        CheckConstraint("code <> ''", name="ck_item_categories_code_not_empty"),
    )


class DataSource(Base, TimestampMixin):
    """Procedência do dado (requisito 17). Toda linha de mercado aponta para uma."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(96), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_community_sourced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
