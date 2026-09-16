"""Leitura das rotas de transporte."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.reference import Location
from app.models.transport import TransportRoute


async def zones_by_pair(session: AsyncSession) -> dict[tuple[str, str], str]:
    """`(slug de origem, slug de destino) -> zona`.

    São 56 linhas para oito locais: carregar tudo de uma vez e resolver em
    memória custa menos que uma consulta por oportunidade, e a arbitragem gera
    milhares delas.
    """
    origem = aliased(Location)
    destino = aliased(Location)

    rows = await session.execute(
        select(origem.slug, destino.slug, TransportRoute.zone)
        .join(origem, TransportRoute.origin_location_id == origem.id)
        .join(destino, TransportRoute.destination_location_id == destino.id)
    )
    return {(o, d): zona for o, d, zona in rows.all()}


async def open_world_slugs(session: AsyncSession) -> frozenset[str]:
    """Locais fora de zona segura, a partir do cadastro.

    Sai de `locations`, não de uma lista no código: qual local está em zona
    aberta é dado de referência. Hoje são o Black Market, pelo `kind`, e
    Caerleon, que é `royal_city` no cadastro mas fica em zona preta no jogo.
    """
    slugs = set(
        (await session.scalars(select(Location.slug).where(Location.kind == "black_market"))).all()
    )
    slugs.add("caerleon")
    return frozenset(slugs)
