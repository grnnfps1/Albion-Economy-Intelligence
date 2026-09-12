"""Metadados para o frontend montar filtros sem hardcode.

Cidades, servidores e categorias vêm do banco. Se o frontend tivesse essa lista
escrita no código, adicionar uma localidade exigiria deploy do frontend
(requisito 6).
"""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.repositories import items as items_repo
from app.repositories import reference as reference_repo
from app.schemas.catalog import (
    CatalogCounts,
    CategoryOut,
    LocationOut,
    MetaResponse,
    ServerOut,
)

router = APIRouter(prefix="/meta", tags=["meta"])

DATA_SOURCE_NOTE = (
    "Dados de mercado vêm de coleta comunitária do Albion Online Data Project: "
    "dependem de jogadores terem aberto o mercado no jogo. Nenhuma cotação é garantida."
)


@router.get("", response_model=MetaResponse)
async def meta(session: SessionDep) -> MetaResponse:
    servers = await reference_repo.list_servers(session)
    locations = await reference_repo.list_locations(session)
    categories = await reference_repo.list_categories(session)
    counts = await items_repo.count_items(session)

    return MetaResponse(
        servers=[ServerOut.model_validate(server) for server in servers],
        locations=[LocationOut.model_validate(location) for location in locations],
        categories=[CategoryOut.model_validate(category) for category in categories],
        tiers=list(range(1, 9)),
        enchantments=list(range(0, 5)),
        qualities=list(range(1, 6)),
        catalog=CatalogCounts(**counts),
        data_source="Albion Online Data Project",
        data_source_note=DATA_SOURCE_NOTE,
    )
