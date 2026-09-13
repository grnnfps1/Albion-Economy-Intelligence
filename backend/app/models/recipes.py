"""Receitas de crafting e refino.

Fonte: `craftingrequirements` do dump oficial do jogo — o mesmo arquivo que o
importador de catálogo já baixa. Não é dado de mercado e não muda com a hora;
muda com patch.

Um item pode ter **mais de uma receita**: `T4_PLANKS` pode ser feito com
2× `T4_WOOD` ou com 1× `T4_WOOD` + 1 token de facção. Por isso `recipes` é uma
tabela, e não colunas em `items`.
"""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Recipe(Base, TimestampMixin):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("output_quantity > 0", name="ck_recipes_output_quantity"),
        CheckConstraint("focus_cost >= 0", name="ck_recipes_focus_cost"),
        Index("ix_recipes_output", "output_item_id"),
        Index("uq_recipes_variant", "output_item_id", "variant_index", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    output_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    # Índice da receita dentro do item, na ordem em que o dump a lista. Torna a
    # reimportação idempotente sem depender do conteúdo.
    variant_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Integer, não SmallInteger: existe receita no dump pedindo 40.000 unidades
    # de um material, e smallint estoura em 32.767. Descoberto importando o dump
    # de verdade, não lendo a documentação.
    output_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    focus_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    silver_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    craft_time: Mapped[float | None] = mapped_column(Numeric(10, 5), nullable=True)
    # `@craftingcategory` do dump: define a estação necessária. NULL quando o
    # dump não informa -- não se inventa estação.
    station_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    materials: Mapped[list["RecipeMaterial"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeMaterial(Base):
    __tablename__ = "recipe_materials"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_recipe_materials_quantity"),
        Index("ix_recipe_materials_item", "item_id"),
    )

    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # O retorno de material só se aplica a recursos elegíveis. Artefato e token
    # não voltam, e tratar todos igual infla o lucro calculado.
    is_returnable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="materials")
