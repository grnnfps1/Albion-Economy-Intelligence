"""Dependências compartilhadas das rotas."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def current_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str | None:
    """Quem está pedindo, segundo o Next.

    O backend **não** valida sessão: quem valida é o `middleware.ts`, e o
    caminho é `Browser → Next → FastAPI` (regra 4). O FastAPI não é exposto ao
    browser, então o cabeçalho só pode ter sido posto pelo Next, que leu o
    cookie assinado.

    Isso é uma decisão de confiança e não um esquecimento: no dia em que o
    backend ficar acessível de fora, este cabeçalho vira autenticação de
    verdade. Enquanto isso ele é `None` em desenvolvimento local, onde não há
    login, e tudo se comporta como antes.
    """
    return (x_user_id or "").strip() or None


SessionDep = Annotated[AsyncSession, Depends(db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[str | None, Depends(current_user_id)]
