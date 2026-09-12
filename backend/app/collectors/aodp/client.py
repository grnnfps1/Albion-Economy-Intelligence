"""Cliente do Albion Online Data Project.

Responsabilidades, nesta ordem:

1. **Não abusar da fonte.** O AODP é comunitário e gratuito. Rate limiter de
   janela dupla, gzip, User-Agent identificável, backoff com jitter no 429.
2. **Não perder a procedência.** Toda resposta pode ser entregue crua, com hash,
   para gravação em `raw_responses` (requisito 17).
3. **Falhar alto em formato inesperado.** Validação estrita; resposta diferente
   do contrato vira erro com o payload preservado, não dado errado no banco.

O que este módulo **não** faz: tocar no banco. Ele devolve objetos validados; a
persistência é do collector (fase 4).
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError
from redis.asyncio import Redis

from app.cache.redis import CACHE_PREFIX
from app.collectors.aodp.batching import batch_item_names, build_url
from app.collectors.aodp.rate_limit import (
    SlidingWindowRateLimiter,
    compute_backoff,
    default_windows,
    parse_retry_after,
)
from app.collectors.aodp.schemas import AodpGoldPoint, AodpHistorySeries, AodpPriceRow
from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

PRICES_PATH = "/api/v2/stats/prices/{item_ids}.json"
HISTORY_PATH = "/api/v2/stats/history/{item_ids}.json"
GOLD_PATH = "/api/v2/stats/gold.json"

VALID_TIMESCALES = (1, 6, 24)


class AodpError(RuntimeError):
    """Falha ao consumir o AODP."""


class AodpRateLimited(AodpError):
    """429 persistente depois de todas as tentativas."""


class AodpInvalidPayload(AodpError):
    """A resposta não bate com o contrato. Guarda o payload para diagnóstico."""

    def __init__(self, message: str, payload: Any) -> None:
        super().__init__(message)
        self.payload = payload


@dataclass
class RawCapture:
    """Resposta crua, pronta para `raw_responses`."""

    endpoint: str
    request_url: str
    http_status: int
    fetched_at: datetime
    payload: Any
    payload_sha256: str


@dataclass
class FetchStats:
    """Contadores de uma sessão de coleta, para `collector_runs`."""

    http_requests: int = 0
    rate_limited: int = 0
    retries: int = 0
    cache_hits: int = 0
    waited_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


def _sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AodpClient:
    """Um cliente por servidor. Os limites do AODP são por host."""

    def __init__(
        self,
        settings: Settings,
        server_code: str,
        http_client: httpx.AsyncClient,
        redis: Redis | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        max_attempts: int = 4,
    ) -> None:
        self.settings = settings
        self.server_code = server_code
        self.base_url = settings.aodp_base_url(server_code)
        self._http = http_client
        self._redis = redis
        self._limiter = rate_limiter or SlidingWindowRateLimiter(
            default_windows(
                settings.aodp_rate_limit_per_minute,
                settings.aodp_rate_limit_per_5_minutes,
            )
        )
        self._max_attempts = max_attempts
        self.stats = FetchStats()

    # ------------------------------------------------------------------ #
    # HTTP
    # ------------------------------------------------------------------ #

    @property
    def _headers(self) -> dict[str, str]:
        return {
            # O projeto pede identificação de quem consome em volume.
            "User-Agent": self.settings.aodp_user_agent,
            # Pedido explícito do AODP: banda não é de graça.
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
        }

    async def _cache_get(self, key: str) -> Any | None:
        if self._redis is None:
            return None
        try:
            cached = await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001 - cache indisponível não derruba a coleta
            log.warning("cache indisponivel na leitura", error=type(exc).__name__)
            return None
        return json.loads(cached) if cached else None

    async def _cache_set(self, key: str, payload: Any) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                key, json.dumps(payload, default=str), ex=self.settings.cache_ttl_seconds
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("cache indisponivel na escrita", error=type(exc).__name__)

    async def _request(
        self, url: str, endpoint: str, use_cache: bool
    ) -> tuple[Any, RawCapture | None]:
        cache_key = f"{CACHE_PREFIX}:aodp:{self.server_code}:{_sha256(url)}"

        if use_cache:
            cached = await self._cache_get(cache_key)
            if cached is not None:
                self.stats.cache_hits += 1
                return cached, None

        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            self.stats.waited_seconds += await self._limiter.acquire()

            try:
                response = await self._http.get(
                    url, headers=self._headers, timeout=self.settings.aodp_timeout_seconds
                )
            except httpx.HTTPError as exc:
                last_error = exc
                self.stats.http_requests += 1
                if attempt == self._max_attempts:
                    break
                self.stats.retries += 1
                await self._backoff(attempt, None)
                continue

            self.stats.http_requests += 1

            if response.status_code == 429:
                self.stats.rate_limited += 1
                last_error = AodpRateLimited(f"429 em {url}")
                if attempt == self._max_attempts:
                    break
                self.stats.retries += 1
                await self._backoff(attempt, parse_retry_after(response.headers.get("Retry-After")))
                continue

            if response.status_code >= 500:
                last_error = AodpError(f"{response.status_code} em {url}")
                if attempt == self._max_attempts:
                    break
                self.stats.retries += 1
                await self._backoff(attempt, None)
                continue

            if response.status_code >= 400:
                # 4xx que não é 429 é erro nosso: repetir não conserta.
                raise AodpError(f"{response.status_code} em {url}")

            try:
                payload = response.json()
            except ValueError as exc:
                raise AodpInvalidPayload(f"resposta não é JSON: {url}", response.text) from exc

            capture = RawCapture(
                endpoint=endpoint,
                request_url=url,
                http_status=response.status_code,
                fetched_at=datetime.now(UTC),
                payload=payload,
                payload_sha256=_sha256(payload),
            )

            if use_cache:
                await self._cache_set(cache_key, payload)

            return payload, capture

        message = f"falha após {self._max_attempts} tentativas: {url}"
        self.stats.errors.append(message)
        if isinstance(last_error, AodpRateLimited):
            raise AodpRateLimited(message) from last_error
        raise AodpError(message) from last_error

    async def _backoff(self, attempt: int, retry_after: float | None) -> None:
        # O servidor sabe melhor que a gente quando voltar.
        delay = retry_after if retry_after is not None else compute_backoff(attempt)
        log.info(
            "aguardando antes de repetir",
            server=self.server_code,
            attempt=attempt,
            delay_seconds=round(delay, 2),
            honoring_retry_after=retry_after is not None,
        )
        self.stats.waited_seconds += delay
        await self._limiter.sleep(delay)

    # ------------------------------------------------------------------ #
    # Endpoints
    # ------------------------------------------------------------------ #

    def _params(self, locations: list[str] | None, qualities: list[int] | None) -> dict[str, str]:
        params: dict[str, str] = {}
        if locations:
            params["locations"] = ",".join(locations)
        if qualities:
            params["qualities"] = ",".join(str(quality) for quality in qualities)
        return params

    async def fetch_prices(
        self,
        item_names: list[str],
        locations: list[str] | None = None,
        qualities: list[int] | None = None,
        use_cache: bool = True,
    ) -> tuple[list[AodpPriceRow], list[RawCapture]]:
        """Preços atuais, em lotes que respeitam o limite de URL."""
        params = self._params(locations, qualities)
        rows: list[AodpPriceRow] = []
        captures: list[RawCapture] = []

        for batch in batch_item_names(
            item_names, self.base_url, PRICES_PATH, params, self.settings.aodp_max_url_length
        ):
            url = build_url(self.base_url, PRICES_PATH, batch, params)
            payload, capture = await self._request(url, "prices", use_cache)
            if capture is not None:
                captures.append(capture)
            rows.extend(self._validate_list(payload, AodpPriceRow, url))

        return rows, captures

    async def fetch_history(
        self,
        item_names: list[str],
        timescale: int = 24,
        locations: list[str] | None = None,
        qualities: list[int] | None = None,
        date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> tuple[list[AodpHistorySeries], list[RawCapture]]:
        """Histórico agregado. Atenção: o AODP agrega **só sell orders**."""
        if timescale not in VALID_TIMESCALES:
            raise ValueError(f"time-scale precisa ser um de {VALID_TIMESCALES}, veio {timescale}")

        params = self._params(locations, qualities)
        params["time-scale"] = str(timescale)
        if date:
            params["date"] = date
        if end_date:
            params["end_date"] = end_date

        series: list[AodpHistorySeries] = []
        captures: list[RawCapture] = []

        for batch in batch_item_names(
            item_names, self.base_url, HISTORY_PATH, params, self.settings.aodp_max_url_length
        ):
            url = build_url(self.base_url, HISTORY_PATH, batch, params)
            payload, capture = await self._request(url, "history", use_cache)
            if capture is not None:
                captures.append(capture)
            series.extend(self._validate_list(payload, AodpHistorySeries, url))

        return series, captures

    async def fetch_gold(
        self,
        count: int | None = None,
        date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> tuple[list[AodpGoldPoint], RawCapture | None]:
        params: dict[str, str] = {}
        if count is not None:
            params["count"] = str(count)
        if date:
            params["date"] = date
        if end_date:
            params["end_date"] = end_date

        url = build_url(self.base_url, GOLD_PATH, [], params)
        payload, capture = await self._request(url, "gold", use_cache)
        return self._validate_list(payload, AodpGoldPoint, url), capture

    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_list(payload: Any, model: type, url: str) -> list:
        if not isinstance(payload, list):
            raise AodpInvalidPayload(f"esperava lista em {url}", payload)
        try:
            return [model.model_validate(entry) for entry in payload]
        except ValidationError as exc:
            raise AodpInvalidPayload(f"payload fora do contrato em {url}: {exc}", payload) from exc
