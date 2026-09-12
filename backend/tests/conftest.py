"""Fixtures de teste.

Regra do projeto (requisito 43): nenhum teste toca a API externa nem precisa de
Postgres/Redis reais. Dependências são substituídas por dublês.
"""

import os

import pytest

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://albion:albion@localhost:5432/albion_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

from app.core.config import Settings  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="development",
        database_url="postgresql+asyncpg://albion:albion@localhost:5432/albion_test",
        redis_url="redis://localhost:6379/1",
        aodp_timeout_seconds=2.0,
    )
