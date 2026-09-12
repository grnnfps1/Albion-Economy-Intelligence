from datetime import UTC, datetime, timedelta

from app.core.freshness import Freshness, classify, data_age_seconds

NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=UTC)
FRESH_LIMIT = 900
STALE_LIMIT = 21600


def test_sem_dado_retorna_none_e_nao_zero():
    """Requisito 52: ausência de dado é UNKNOWN, nunca 0."""
    assert data_age_seconds(None, NOW) is None
    assert classify(None, FRESH_LIMIT, STALE_LIMIT) is Freshness.UNKNOWN


def test_timestamp_naive_e_tratado_como_utc():
    """O AODP devolve timestamps sem fuso, e eles são UTC (docs/02-aodp.md)."""
    naive = datetime(2026, 9, 12, 11, 50, 0)
    assert data_age_seconds(naive, NOW) == 600


def test_classificacao_por_faixa():
    assert classify(0, FRESH_LIMIT, STALE_LIMIT) is Freshness.FRESH
    assert classify(FRESH_LIMIT, FRESH_LIMIT, STALE_LIMIT) is Freshness.FRESH
    assert classify(FRESH_LIMIT + 1, FRESH_LIMIT, STALE_LIMIT) is Freshness.STALE
    assert classify(STALE_LIMIT, FRESH_LIMIT, STALE_LIMIT) is Freshness.STALE
    assert classify(STALE_LIMIT + 1, FRESH_LIMIT, STALE_LIMIT) is Freshness.OLD


def test_data_futura_nao_gera_idade_negativa():
    future = NOW + timedelta(minutes=5)
    assert data_age_seconds(future, NOW) == 0
