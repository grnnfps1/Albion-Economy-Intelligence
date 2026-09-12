from fastapi import APIRouter

from app.api.v1.routes import items, meta

# Rotas de negócio, versionadas sob /api/v1.
api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(items.router)
