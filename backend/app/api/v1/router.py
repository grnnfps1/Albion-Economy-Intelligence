from fastapi import APIRouter

from app.api.v1.routes import (
    arbitrage,
    crafting,
    dashboard,
    farming,
    focus,
    history,
    items,
    market,
    meta,
    refining,
)

# Rotas de negócio, versionadas sob /api/v1.
api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(meta.router)
api_router.include_router(items.router)
api_router.include_router(market.router)
api_router.include_router(history.router)
api_router.include_router(arbitrage.router)
api_router.include_router(crafting.router)
api_router.include_router(refining.router)
api_router.include_router(focus.router)
api_router.include_router(farming.router)
