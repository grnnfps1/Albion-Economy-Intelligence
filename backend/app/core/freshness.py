"""Classificação de idade do dado.

Função pura: entra timestamp, sai status. Sem I/O, sem relógio implícito -- o
"agora" é sempre passado pelo chamador, o que torna o teste determinístico.
"""

from datetime import UTC, datetime
from enum import StrEnum


class Freshness(StrEnum):
    FRESH = "ATUALIZADO"
    STALE = "DESATUALIZADO"
    OLD = "ANTIGO"
    UNKNOWN = "DESCONHECIDO"


def data_age_seconds(observed_at: datetime | None, now: datetime) -> int | None:
    """Idade em segundos, ou None quando não há dado.

    Ausência de dado é None -- nunca 0 (requisito 52).
    """
    if observed_at is None:
        return None
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    return max(0, int((now - observed_at).total_seconds()))


def classify(age_seconds: int | None, fresh_limit: int, stale_limit: int) -> Freshness:
    if age_seconds is None:
        return Freshness.UNKNOWN
    if age_seconds <= fresh_limit:
        return Freshness.FRESH
    if age_seconds <= stale_limit:
        return Freshness.STALE
    return Freshness.OLD
