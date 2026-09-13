"""Configuração da aplicação.

Única fonte de verdade para variáveis de ambiente. Nenhum módulo lê os.environ
diretamente -- isso mantém o inventário de configuração em um lugar só e torna
os testes previsíveis.
"""

import json
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- identidade ---------------------------------------------------------
    app_name: str = "Albion Economy Intelligence"
    api_v1_prefix: str = "/api/v1"
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = False

    # --- infraestrutura -----------------------------------------------------
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://albion:albion@localhost:5432/albion"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # --- web ----------------------------------------------------------------
    # `NoDecode` é obrigatório aqui. Sem ele, o pydantic-settings tenta ler a
    # variável de ambiente como JSON *antes* de qualquer validador rodar, e
    # `CORS_ORIGINS=http://localhost:3000` derruba a aplicação no startup com um
    # erro que não diz o que fazer. Com `NoDecode`, o valor chega cru ao
    # validador abaixo, que aceita a forma que uma pessoa escreveria num .env.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- AODP ---------------------------------------------------------------
    # Hosts verificados em 2026-09-12. Ver docs/02-aodp.md.
    aodp_base_urls: dict[str, str] = Field(
        default_factory=lambda: {
            "west": "https://west.albion-online-data.com",
            "east": "https://east.albion-online-data.com",
            "europe": "https://europe.albion-online-data.com",
        }
    )
    aodp_default_server: str = "west"
    aodp_timeout_seconds: float = 15.0
    aodp_user_agent: str = "AlbionEconomyIntelligence/0.1 (+contato: configure AODP_USER_AGENT)"
    # Limites documentados pelo AODP. 300/5min é o limite efetivo: 1 req/s sustentado.
    aodp_rate_limit_per_minute: int = 180
    aodp_rate_limit_per_5_minutes: int = 300
    aodp_max_url_length: int = 4096

    # --- cache --------------------------------------------------------------
    cache_ttl_seconds: int = 60

    # --- frescor do dado (requisito 4) --------------------------------------
    freshness_fresh_seconds: int = 900        # <= 15 min  -> ATUALIZADO
    freshness_stale_seconds: int = 21600      # <= 6 h     -> DESATUALIZADO; acima -> ANTIGO

    # --- modo mock (requisito 44) -------------------------------------------
    use_mock_data: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Aceita as duas formas que aparecem num .env.

        A separada por vírgula é a que uma pessoa escreve:
            CORS_ORIGINS=http://localhost:3000, https://app.exemplo.com

        A JSON é a que ferramentas de deploy costumam gerar:
            CORS_ORIGINS=["http://localhost:3000"]

        Recusar qualquer uma das duas seria uma armadilha silenciosa no deploy.
        """
        if not isinstance(value, str):
            return value

        texto = value.strip()
        if texto.startswith("["):
            try:
                decodificado = json.loads(texto)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"CORS_ORIGINS parece JSON mas não é válido: {exc}"
                ) from exc
            return [str(item).strip() for item in decodificado if str(item).strip()]

        return [item.strip() for item in texto.split(",") if item.strip()]

    @model_validator(mode="after")
    def _forbid_mock_in_production(self) -> "Settings":
        if self.environment is Environment.PRODUCTION and self.use_mock_data:
            raise ValueError(
                "USE_MOCK_DATA=true é proibido em ENVIRONMENT=production. "
                "Dado mock nunca pode ser servido como dado real (requisito 44)."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def aodp_base_url(self, server_code: str) -> str:
        try:
            return self.aodp_base_urls[server_code]
        except KeyError as exc:
            known = ", ".join(sorted(self.aodp_base_urls))
            raise ValueError(
                f"servidor desconhecido: {server_code!r}. Conhecidos: {known}"
            ) from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()
