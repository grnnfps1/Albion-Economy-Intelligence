"""Catálogo de itens."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Item(Base, TimestampMixin):
    """Item do jogo.

    `unique_name` é a chave lógica (requisito 10): é o id técnico usado pelo AODP
    e pelo dump oficial, e é o que vai na URL da requisição. O nome visual é
    apresentação e muda por idioma e por patch -- nunca é usado em join.

    Formatos reais de `unique_name` (verificados em formatted/items.txt):
        T4_PLANKS            base
        T4_BAG@1             equipamento encantado
        T4_PLANKS_LEVEL1@1   recurso refinado encantado
    """

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("tier IS NULL OR tier BETWEEN 1 AND 8", name="ck_items_tier"),
        CheckConstraint("enchantment BETWEEN 0 AND 4", name="ck_items_enchantment"),
        CheckConstraint(
            "max_quality IS NULL OR max_quality BETWEEN 1 AND 5", name="ck_items_max_quality"
        ),
        Index("ix_items_base_name", "base_name"),
        Index("ix_items_tier_enchantment", "tier", "enchantment"),
        Index("ix_items_category", "category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unique_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    base_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # NULL quando o dump não informa. Nunca chutar um tier (requisito 52).
    tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    enchantment: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    category_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True
    )
    subcategory_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    display_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name_pt: Mapped[str | None] = mapped_column(String(255), nullable=True)

    weight: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_quality: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Ração: `@nutrition` e `@foodcategory` do dump. Só existem em cultivo,
    # carne e animal adulto, e são o que liga um filhote ao que ele come --
    # sem isso não dá para custear uma criação sem chutar a quantidade.
    nutrition: Mapped[int | None] = mapped_column(Integer, nullable=True)
    food_category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Marca o subconjunto que os collectors varrem. Varrer 12 mil itens a 1 req/s
    # não fecha a conta (risco R5); a coleta é priorizada por este campo.
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
