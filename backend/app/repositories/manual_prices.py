"""Leitura e escrita de preço manual.

Único lugar com SQL de `manual_prices`, como manda a dependência
`api → services → repositories → db`.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Item
from app.models.manual_price import KINDS, ManualPrice
from app.models.reference import Location, Server


async def upsert(
    session: AsyncSession,
    user_id: str,
    server_code: str,
    location_slug: str,
    item_unique_name: str,
    quality: int,
    price: int,
    kind: str,
) -> ManualPrice | None:
    """Grava ou atualiza o preço manual de uma ponta.

    Reinformar **renova a idade**: o usuário acabou de olhar o mercado, e a
    idade exibida precisa refletir isso. É o que permite ao preço manual
    envelhecer como qualquer cotação em vez de virar verdade permanente.

    Devolve `None` quando servidor, cidade ou item não existem — quem chama
    transforma em 404 em vez de gravar uma linha órfã.
    """
    if kind not in KINDS:
        return None

    ids = await _resolve_ids(session, server_code, location_slug, item_unique_name)
    if ids is None:
        return None
    server_id, location_id, item_id = ids

    agora = datetime.now(UTC)
    statement = (
        pg_insert(ManualPrice)
        .values(
            user_id=user_id, server_id=server_id, location_id=location_id,
            item_id=item_id, quality=quality, price=price, kind=kind,
            created_at=agora, updated_at=agora,
        )
        .on_conflict_do_update(
            constraint="uq_manual_prices_chave",
            set_={"price": price, "created_at": agora, "updated_at": agora},
        )
        .returning(ManualPrice)
    )
    # `populate_existing` porque o objeto já pode estar no identity map da
    # sessão: sem isso, reinformar devolveria o preço **antigo** — o banco
    # atualizado e o objeto em memória discordando em silêncio.
    return (
        await session.execute(
            statement, execution_options={"populate_existing": True}
        )
    ).scalar_one()


async def remove(
    session: AsyncSession,
    user_id: str,
    server_code: str,
    location_slug: str,
    item_unique_name: str,
    quality: int,
    kind: str,
) -> int:
    """Apaga o preço manual. Apagar é como se diz 'volte a usar o coletado'."""
    ids = await _resolve_ids(session, server_code, location_slug, item_unique_name)
    if ids is None:
        return 0
    server_id, location_id, item_id = ids

    resultado = await session.execute(
        delete(ManualPrice).where(
            ManualPrice.user_id == user_id,
            ManualPrice.server_id == server_id,
            ManualPrice.location_id == location_id,
            ManualPrice.item_id == item_id,
            ManualPrice.quality == quality,
            ManualPrice.kind == kind,
        )
    )
    return int(resultado.rowcount or 0)


async def list_for_user(
    session: AsyncSession, user_id: str, server_code: str | None = None
) -> list[tuple[ManualPrice, Item, Location]]:
    """Tudo que o usuário informou, para a tela poder listar e apagar."""
    statement = (
        select(ManualPrice, Item, Location)
        .join(Item, ManualPrice.item_id == Item.id)
        .join(Location, ManualPrice.location_id == Location.id)
        .join(Server, ManualPrice.server_id == Server.id)
        .where(ManualPrice.user_id == user_id)
        .order_by(Item.unique_name, Location.slug, ManualPrice.kind)
    )
    if server_code:
        statement = statement.where(Server.code == server_code)
    return list((await session.execute(statement)).all())


async def load_overrides(
    session: AsyncSession, user_id: str | None, server_code: str
) -> dict[tuple[str, str, int, str], tuple[int, datetime]]:
    """`(item, cidade, qualidade, kind) -> (preço, quando foi informado)`.

    Devolve **tudo**, inclusive o que já passou do limite de frescor: quem
    decide se ainda vale é `ManualPriceOverlay`, que tem o relógio e o limite.
    Filtrar aqui esconderia do usuário que existe um preço manual velho para
    aquele item — e ele precisa saber, para atualizar ou apagar.
    """
    if not user_id:
        return {}

    linhas = await session.execute(
        select(
            Item.unique_name, Location.slug, ManualPrice.quality,
            ManualPrice.kind, ManualPrice.price, ManualPrice.created_at,
        )
        .join(Item, ManualPrice.item_id == Item.id)
        .join(Location, ManualPrice.location_id == Location.id)
        .join(Server, ManualPrice.server_id == Server.id)
        .where(ManualPrice.user_id == user_id, Server.code == server_code)
    )
    return {
        (item, slug, quality, kind): (price, created_at)
        for item, slug, quality, kind, price, created_at in linhas.all()
    }


async def _resolve_ids(
    session: AsyncSession, server_code: str, location_slug: str, item_unique_name: str
) -> tuple[int, int, int] | None:
    server_id = await session.scalar(select(Server.id).where(Server.code == server_code))
    location_id = await session.scalar(
        select(Location.id).where(Location.slug == location_slug)
    )
    item_id = await session.scalar(
        select(Item.id).where(Item.unique_name == item_unique_name)
    )
    if server_id is None or location_id is None or item_id is None:
        return None
    return server_id, location_id, item_id
