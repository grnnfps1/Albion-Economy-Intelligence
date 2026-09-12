"""Base declarativa do SQLAlchemy.

Os modelos entram na FASE 2. Esta classe existe agora para que o Alembic já
tenha um `target_metadata` estável e as migrations nasçam no lugar certo.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
