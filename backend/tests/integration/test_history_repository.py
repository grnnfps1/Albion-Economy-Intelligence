"""Histórico e gold contra PostgreSQL, incluindo marcação de outlier."""

from datetime import UTC, datetime, timedelta

import pytest

from app.calculations.statistics import flag_outliers
from app.collectors.aodp.normalization import GoldPriceRecord, MarketHistoryRecord
from app.models.catalog import Item
from app.models.reference import DataSource, Location, Server
from app.repositories import history as history_repo
from app.services.history_service import build_series

pytestmark = pytest.mark.asyncio

BASE = datetime(2026, 8, 13, tzinfo=UTC)
# Série real de T4_BAG q2 em Lymhurst, com o pico de 16/08.
PRECOS = [3716, 3525, 3625, 29790, 3737, 3701, 3718, 3847, 3919, 3895]


@pytest.fixture
async def fixtures(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    lymhurst = Location(
        aodp_name="Lymhurst", slug="lymhurst", display_name="Lymhurst", kind="royal_city"
    )
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    bag = Item(unique_name="T4_BAG", base_name="T4_BAG", tier=4, enchantment=0,
               display_name_pt="Bolsa", is_tracked=True)
    session.add_all([server, lymhurst, source, bag])
    await session.flush()
    return {"server": server, "location": lymhurst, "source": source, "item": bag}


def registros(fixtures, precos=PRECOS):
    return [
        MarketHistoryRecord(
            server_id=fixtures["server"].id,
            location_id=fixtures["location"].id,
            item_id=fixtures["item"].id,
            quality=2, timescale=24,
            bucket_ts=BASE + timedelta(days=index),
            item_count=1000, avg_price=preco,
            source_id=fixtures["source"].id, ingested_at=BASE,
        )
        for index, preco in enumerate(precos)
    ]


async def test_upsert_e_idempotente(session, fixtures):
    assert await history_repo.upsert_history(session, registros(fixtures)) == 10
    await history_repo.upsert_history(session, registros(fixtures))
    assert await history_repo.count_history(session, "west") == 10


async def test_recoleta_atualiza_o_bucket(session, fixtures):
    await history_repo.upsert_history(session, registros(fixtures))
    revisado = list(PRECOS)
    revisado[0] = 4000
    await history_repo.upsert_history(session, registros(fixtures, revisado))

    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)
    assert rows[0][0].avg_price == 4000


async def test_outlier_e_marcado_e_nao_apagado(session, fixtures):
    """O pico de 29.790 fica gravado, apenas sinalizado."""
    await history_repo.upsert_history(session, registros(fixtures))
    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)

    records = [record for record, _location in rows]
    flags = flag_outliers([float(r.avg_price) for r in records])
    marks = {
        (r.server_id, r.location_id, r.item_id, r.quality, r.timescale, r.bucket_ts): flag
        for r, flag in zip(records, flags, strict=True)
    }
    assert await history_repo.mark_outliers(session, marks) == 1

    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)
    marcados = [record for record, _ in rows if record.is_outlier]
    assert len(marcados) == 1
    assert marcados[0].avg_price == 29790
    assert await history_repo.count_history(session, "west") == 10


async def test_marcacao_repetida_nao_reescreve(session, fixtures):
    await history_repo.upsert_history(session, registros(fixtures))
    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)
    records = [record for record, _ in rows]
    flags = flag_outliers([float(r.avg_price) for r in records])
    marks = {
        (r.server_id, r.location_id, r.item_id, r.quality, r.timescale, r.bucket_ts): flag
        for r, flag in zip(records, flags, strict=True)
    }
    await history_repo.mark_outliers(session, marks)
    assert await history_repo.mark_outliers(session, marks) == 0


async def test_resumo_da_serie_ignora_o_outlier(session, fixtures):
    await history_repo.upsert_history(session, registros(fixtures))
    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)
    records = [record for record, _ in rows]
    flags = flag_outliers([float(r.avg_price) for r in records])
    await history_repo.mark_outliers(
        session,
        {
            (r.server_id, r.location_id, r.item_id, r.quality, r.timescale, r.bucket_ts): f
            for r, f in zip(records, flags, strict=True)
        },
    )

    rows = await history_repo.load_series(session, "west", "T4_BAG", timescale=24)
    series = build_series(rows)

    assert len(series) == 1
    serie = series[0]
    assert serie.outlier_count == 1
    assert len(serie.points) == 10          # o ponto continua visível
    assert serie.maximum == 3919            # mas fora da estatística
    assert serie.median is not None and serie.median < 4000


async def test_gold_upsert_e_leitura(session, fixtures):
    registros_gold = [
        GoldPriceRecord(
            server_id=fixtures["server"].id,
            ts=BASE + timedelta(hours=hora),
            price=8000 + hora * 5,
            source_id=fixtures["source"].id,
        )
        for hora in range(5)
    ]
    assert await history_repo.upsert_gold(session, registros_gold) == 5
    await history_repo.upsert_gold(session, registros_gold)

    rows = await history_repo.load_gold(session, "west")
    assert len(rows) == 5
    assert rows[0].ts < rows[-1].ts        # ordem cronológica para o gráfico
