"""Agricultura e criação de animais.

Fonte: `farmableitem` do dump oficial — o mesmo arquivo que o importador de
catálogo já baixa — mais `loot.json`, que é onde o dump guarda o que cada
colheita de fato entrega.

Duas coisas separam isto de crafting e precisam estar no schema, não no cálculo:

1. **Tempo.** Um ciclo de fazenda leva 22 horas (`activefarmcyclelengthseconds`
   = 79200) e um filhote de montaria leva quase um mês. Comparar "lucro por
   ciclo" de fazenda com "lucro por craft" não significa nada: só prata por dia
   compara os dois. Por isso a duração é coluna, não constante no código.

2. **Ração.** Um filhote consome cultivo enquanto cresce, e a quantidade sai de
   `nutritionmax` e `secondspernutrition`. É o que transforma criação numa
   cadeia — semente → cultivo → filhote → adulto — e é por isso que
   `calculations/chain.py`, escrito para refino, resolve este formato também.

O que o dump **não** decide fica `NULL` e vai para `docs/04-taxas.md`, não vira
um número plausível escrito à mão.
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

# `@shopsubcategory1` do dump. Não são inventados aqui.
FARM_STATIONS = ("farm", "herbgarden", "pasture", "kennel")

# Papel do item dentro do ciclo, de `@shopsubcategory2`: semente, filhote ou
# adulto. Um adulto pode ser produto final (vendido) e insumo (dá leite/ovo).
FARM_ROLES = ("seed", "baby", "grown")

# O que cada saída significa. Um ciclo entrega mais de uma coisa: a colheita
# principal, a semente que às vezes volta e o filhote que às vezes nasce.
OUTPUT_ROLES = ("harvest", "product", "grown", "seed_return", "offspring")


class Farmable(Base, TimestampMixin):
    """Uma coisa que se planta ou se cria, com o tempo que ela leva."""

    __tablename__ = "farmables"
    __table_args__ = (
        CheckConstraint("station IN " + str(FARM_STATIONS), name="ck_farmables_station"),
        CheckConstraint("role IN " + str(FARM_ROLES), name="ck_farmables_role"),
        CheckConstraint(
            "cycle_seconds IS NULL OR cycle_seconds > 0", name="ck_farmables_cycle_seconds"
        ),
        Index("ix_farmables_station", "station"),
        Index("ix_farmables_item", "item_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    station: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    # Duração do ciclo de Focus (`activefarmcyclelengthseconds`): 79200 s = 22 h.
    cycle_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Quanto tempo até colher ou até o filhote virar adulto. É o que divide o
    # lucro para virar prata por dia.
    grow_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Adulto que produz leite/ovo: intervalo entre produções.
    product_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    focus_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_cycles: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # `@activefarmbonus`. Guardado porque está no dump, **não** usado no
    # cálculo: o que ele multiplica não foi verificado no jogo. Ver
    # docs/04-taxas.md.
    active_farm_bonus: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Preço fixo do comerciante de fazenda (`craftingrequirements.@silver`).
    # É a alternativa ao mercado para comprar semente e filhote.
    npc_silver_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grown_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )

    # Ração: um ponto de nutrição a cada `seconds_per_nutrition` segundos.
    # O total de uma criação é `grow_seconds / seconds_per_nutrition`.
    accepted_food_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seconds_per_nutrition: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    nutrition_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favorite_food_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    outputs: Mapped[list["FarmableOutput"]] = relationship(
        back_populates="farmable", cascade="all, delete-orphan", lazy="selectin"
    )


class FarmableOutput(Base):
    """O que um ciclo entrega.

    A quantidade é **faixa**, não número: o dump diz `3-6` cenouras por pé. A
    faixa fica nas duas colunas e o cálculo usa a média — achatar para um único
    valor aqui apagaria a incerteza antes de alguém poder vê-la.
    """

    __tablename__ = "farmable_outputs"
    __table_args__ = (
        CheckConstraint("role IN " + str(OUTPUT_ROLES), name="ck_farmable_outputs_role"),
        CheckConstraint("amount_min >= 0 AND amount_max >= amount_min",
                        name="ck_farmable_outputs_amount"),
        CheckConstraint("chance >= 0 AND chance <= 1", name="ck_farmable_outputs_chance"),
        Index("uq_farmable_outputs", "farmable_id", "item_id", "role", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmable_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("farmables.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_min: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_max: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chance: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=1)

    farmable: Mapped[Farmable] = relationship(back_populates="outputs")
