"""Leitura dos parâmetros de configuração."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import ConfigParameter


async def get_values(session: AsyncSession, keys: list[str]) -> dict[str, Any]:
    """Devolve `chave -> valor`. Chave com `value` nulo **não** entra no dicionário.

    Isso é deliberado: quem chama distingue "não configurado" de "configurado
    como zero" pela ausência da chave, e não precisa saber que existe uma coluna
    `source` com 'UNKNOWN'.
    """
    rows = await session.execute(
        select(ConfigParameter.key, ConfigParameter.value).where(
            ConfigParameter.key.in_(keys)
        )
    )
    return {key: value for key, value in rows.all() if value is not None}


async def get_value(session: AsyncSession, key: str, default: Any = None) -> Any:
    return (await get_values(session, [key])).get(key, default)
