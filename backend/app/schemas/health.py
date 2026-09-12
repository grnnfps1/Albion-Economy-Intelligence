from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "degraded", "down"]


class ComponentHealth(BaseModel):
    status: CheckStatus
    latency_ms: int | None = None
    detail: str | None = None


class AodpServerHealth(BaseModel):
    server: str
    status: CheckStatus
    status_code: int | None = None
    latency_ms: int | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: CheckStatus
    app: str
    environment: str
    version: str
    mock_data: bool = Field(
        description="true quando a instância pode servir dado mock (requisito 44)"
    )


class DatabaseHealthResponse(BaseModel):
    status: CheckStatus
    database: ComponentHealth
    cache: ComponentHealth


class AodpHealthResponse(BaseModel):
    status: CheckStatus
    source: str = "albion-online-data-project"
    community_sourced: bool = True
    servers: list[AodpServerHealth]
