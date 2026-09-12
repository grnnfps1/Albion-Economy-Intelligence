from fastapi import APIRouter, Response

from app.cache.redis import get_redis
from app.core.config import get_settings
from app.db.session import get_engine
from app.schemas.health import (
    AodpHealthResponse,
    DatabaseHealthResponse,
    HealthResponse,
)
from app.services import health_service

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness. Não toca em dependência externa -- responde se o processo vive."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=str(settings.environment),
        version=VERSION,
        mock_data=settings.use_mock_data,
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def health_database(response: Response) -> DatabaseHealthResponse:
    """Readiness: PostgreSQL e Redis."""
    database = await health_service.check_database(get_engine())
    cache = await health_service.check_cache(get_redis())
    status = health_service.worst([database.status, cache.status])
    if status != "ok":
        response.status_code = 503
    return DatabaseHealthResponse(status=status, database=database, cache=cache)


@router.get("/health/aodp", response_model=AodpHealthResponse)
async def health_aodp(response: Response) -> AodpHealthResponse:
    """Disponibilidade da fonte de dados comunitária."""
    settings = get_settings()
    servers = await health_service.check_aodp(settings)
    status = health_service.worst([server.status for server in servers])
    if status == "down":
        response.status_code = 503
    return AodpHealthResponse(status=status, servers=servers)
