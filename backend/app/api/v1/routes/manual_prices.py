"""Preço manual: a sobrescrita do usuário sobre a cotação coletada."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep, SettingsDep, UserDep
from app.catalog.icons import item_icon_url
from app.models.manual_price import KINDS
from app.repositories import manual_prices as manual_repo
from app.schemas.manual_price import ManualPriceIn, ManualPriceList, ManualPriceOut

router = APIRouter(prefix="/manual-prices", tags=["manual-prices"])

SEM_USUARIO = (
    "Preço manual precisa de sessão: ele é por usuário. Sem DISCORD_CLIENT_ID e "
    "SESSION_SECRET a aplicação roda aberta e não há a quem atribuir o preço."
)


def _exige_usuario(user_id: str | None) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail=SEM_USUARIO)
    return user_id


@router.get("", response_model=ManualPriceList)
async def listar(
    session: SessionDep,
    settings: SettingsDep,
    user_id: UserDep,
    server: str = Query("west"),
) -> ManualPriceList:
    """Tudo que o usuário informou, com a idade de cada preço."""
    dono = _exige_usuario(user_id)
    linhas = await manual_repo.list_for_user(session, dono, server)
    agora = datetime.now(UTC)
    limite = settings.freshness_stale_seconds

    return ManualPriceList(
        server=server,
        total=len(linhas),
        max_age_seconds=limite,
        prices=[_out(p, item, local, server, agora, limite) for p, item, local in linhas],
    )


@router.put("", response_model=ManualPriceOut, status_code=200)
async def gravar(
    session: SessionDep, settings: SettingsDep, user_id: UserDep, payload: ManualPriceIn
) -> ManualPriceOut:
    """Grava ou atualiza. Reinformar renova a idade.

    Renovar a idade é deliberado: quem reinforma acabou de olhar o mercado, e é
    exatamente a informação que a idade exibida precisa carregar.
    """
    dono = _exige_usuario(user_id)
    if payload.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind precisa ser um de {KINDS}")

    linha = await manual_repo.upsert(
        session, dono, payload.server, payload.location, payload.item,
        payload.quality, payload.price, payload.kind,
    )
    if linha is None:
        raise HTTPException(
            status_code=404, detail="servidor, cidade ou item não encontrado"
        )
    await session.commit()

    linhas = await manual_repo.list_for_user(session, dono, payload.server)
    agora = datetime.now(UTC)
    for p, item, local in linhas:
        if item.unique_name == payload.item and local.slug == payload.location \
                and p.quality == payload.quality and p.kind == payload.kind:
            return _out(p, item, local, payload.server, agora,
                        settings.freshness_stale_seconds)
    raise HTTPException(status_code=500, detail="preço gravado mas não relido")


@router.delete("", status_code=204)
async def apagar(
    session: SessionDep,
    user_id: UserDep,
    server: str = Query("west"),
    location: str = Query(...),
    item: str = Query(...),
    quality: int = Query(1, ge=1, le=5),
    kind: str = Query(...),
) -> None:
    """Apagar é como se diz 'volte a usar o preço coletado'."""
    dono = _exige_usuario(user_id)
    removidos = await manual_repo.remove(
        session, dono, server, location, item, quality, kind
    )
    if not removidos:
        raise HTTPException(status_code=404, detail="preço manual não encontrado")
    await session.commit()


def _out(price, item, location, server: str, agora, limite: int) -> ManualPriceOut:
    idade = max(0, int((agora - price.created_at).total_seconds()))
    return ManualPriceOut(
        server=server,
        location=location.slug,
        location_name=location.display_name,
        item=item.unique_name,
        item_name=item.display_name_pt or item.display_name_en,
        icon_url=item_icon_url(item.unique_name, price.quality),
        quality=price.quality,
        price=price.price,
        kind=price.kind,
        informed_at=price.created_at.isoformat(),
        age_seconds=idade,
        is_stale=idade > limite,
    )
