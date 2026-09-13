"""Consulta ao catálogo de itens."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep
from app.catalog.icons import item_icon_url
from app.repositories import items as items_repo
from app.schemas.catalog import ItemOut, ItemPage

router = APIRouter(prefix="/items", tags=["items"])


def _with_icon(row) -> ItemOut:
    out = ItemOut.model_validate(row)
    out.icon_url = item_icon_url(row.unique_name)
    return out


@router.get("", response_model=ItemPage)
async def list_items(
    session: SessionDep,
    search: str | None = Query(None, description="Busca no id técnico e nos nomes visuais."),
    tier: int | None = Query(None, ge=1, le=8),
    enchantment: int | None = Query(None, ge=0, le=4),
    category: str | None = Query(None, description="Código da categoria, ex.: crafting."),
    tracked_only: bool = Query(False, description="Só itens varridos pelos collectors."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ItemPage:
    rows, total = await items_repo.search_items(
        session,
        search=search,
        tier=tier,
        enchantment=enchantment,
        category_code=category,
        tracked_only=tracked_only,
        limit=limit,
        offset=offset,
    )
    return ItemPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[_with_icon(row) for row in rows],
    )


@router.get("/{unique_name}", response_model=ItemOut)
async def get_item(session: SessionDep, unique_name: str) -> ItemOut:
    item = await items_repo.get_by_unique_name(session, unique_name)
    if item is None:
        raise HTTPException(status_code=404, detail=f"item não encontrado: {unique_name}")
    return _with_icon(item)
