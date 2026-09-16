"""Rotas de transporte entre mercados.

Uma linha por par origem-destino. O que ela carrega de verdade é a **zona**: é a
diferença entre uma viagem entre cidades reais e uma que atravessa zona aberta,
onde a carga inteira pode não chegar.

A classificação é por **pontas**, não por caminho percorrido. O caminho é
escolha do jogador — dá para ir de Martlock a Caerleon por rotas diferentes — e
o dado que temos são os dois mercados. Qualquer ponta em Caerleon ou no Black
Market atravessa vermelha ou preta; cidade real para cidade real é azul.

`is_manual` existe para o caso em que a regra genérica erra. Brecilien é o
exemplo conhecido: está em `locations` como `royal_city`, mas só se chega por
portal das Brumas, e classificá-la como azul é a leitura otimista. Uma linha com
`is_manual = true` não é sobrescrita pelo seed.
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

# Os valores de `calculations/risk.py::Zone`. Ficam repetidos aqui porque o
# CHECK é do banco e não pode importar Python — e há teste que falha se os dois
# conjuntos divergirem.
ZONES = ("MESMA_CIDADE", "AZUL", "VERMELHA_PRETA")


class TransportRoute(Base, TimestampMixin):
    __tablename__ = "transport_routes"
    __table_args__ = (
        CheckConstraint("zone IN " + str(ZONES), name="ck_transport_routes_zone"),
        CheckConstraint(
            "origin_location_id <> destination_location_id",
            name="ck_transport_routes_distintos",
        ),
        Index(
            "uq_transport_routes_par",
            "origin_location_id",
            "destination_location_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_location_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    destination_location_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )

    zone: Mapped[str] = mapped_column(String(16), nullable=False)

    # Os três campos que o modelo de dados previa desde a fase 0 e que continuam
    # sem medição. NULL, nunca um número plausível: distância inventada viraria
    # componente de score inventado.
    distance_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_cost_per_weight: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Linha ajustada à mão não é sobrescrita pelo seed, do mesmo jeito que
    # `items.is_tracked` não é sobrescrito por reimportação de catálogo.
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
