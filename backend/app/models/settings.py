"""Parâmetros de negócio versionados em banco.

Taxa nunca é hardcode dentro de fórmula (requisito 26). As funções de
`calculations/` recebem os valores daqui como argumento.
"""

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ConfigParameter(Base, TimestampMixin):
    __tablename__ = "config_parameters"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # De onde veio o número. "UNKNOWN" significa que ainda não foi verificado no
    # jogo e que quem consumir precisa tratar como desconhecido.
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="UNKNOWN")
