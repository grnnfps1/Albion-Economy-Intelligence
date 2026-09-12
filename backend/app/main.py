"""Ponto de entrada da API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routes import health
from app.cache.redis import close_redis, init_redis
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, init_engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()
    configure_logging(settings)

    init_engine(settings)
    init_redis(settings)

    log.info(
        "aplicacao iniciada",
        environment=str(settings.environment),
        mock_data=settings.use_mock_data,
        aodp_servers=list(settings.aodp_base_urls),
    )
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        log.info("aplicacao encerrada")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=health.VERSION,
        description=(
            "Motor de inteligência econômica para Albion Online. "
            "Fonte de mercado: Albion Online Data Project (coleta comunitária)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # /health* fora do prefixo versionado: é infraestrutura, não contrato de produto.
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
