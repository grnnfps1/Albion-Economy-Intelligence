"""Fixtures de integração.

Estes testes precisam de PostgreSQL. Eles pulam sozinhos quando o banco não está
disponível, para que `pytest` continue rodando na máquina de quem não subiu o
compose -- mas nunca passam silenciosamente fingindo ter testado.

O banco usado é o de `TEST_DATABASE_URL` (padrão: albion_test). Cada teste roda
dentro de uma transação que sofre rollback no fim: a suíte não deixa resíduo.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://albion:albion@localhost:5432/albion_test"
)

_schema_created = False


@pytest_asyncio.fixture
async def engine():
    global _schema_created

    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        if not _schema_created:
            async with engine.begin() as connection:
                # O schema de teste sai dos modelos, não das migrations: o que se
                # testa aqui é o comportamento das queries. A validade das
                # migrations é verificada rodando `alembic upgrade head`
                # (ver tests/integration/test_reference_seed.py e o README).
                await connection.run_sync(Base.metadata.create_all)
            _schema_created = True
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL indisponível em {TEST_DATABASE_URL}: {type(exc).__name__}")

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Sessão com rollback garantido no fim do teste."""
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async with factory() as db_session:
        yield db_session
    await transaction.rollback()
    await connection.close()
