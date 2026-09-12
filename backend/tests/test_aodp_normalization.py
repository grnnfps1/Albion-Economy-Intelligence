"""Normalização das respostas do AODP.

Os payloads abaixo são recortes fiéis de respostas reais verificadas em
2026-09-12, inclusive a sentinela de "não há ordem".
"""

from datetime import UTC, datetime

import pytest

from app.collectors.aodp.normalization import (
    GoldPriceRecord,
    MarketPriceRecord,
    RejectedRow,
    is_sentinel_date,
    normalize_gold_point,
    normalize_history_series,
    normalize_price,
    normalize_price_row,
    to_utc,
)
from app.collectors.aodp.schemas import AodpGoldPoint, AodpHistorySeries, AodpPriceRow

LOCATIONS = {"Caerleon": 1, "Fort Sterling": 2, "Black Market": 3}
ITEMS = {"T4_BAG": 10, "T5_LEATHER": 11}
OBSERVED = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)

# Resposta real: T4_BAG em Caerleon. Sem ordem de compra -- sentinela nos dois
# campos de buy.
REAL_PRICE_ROW = {
    "item_id": "T4_BAG",
    "city": "Caerleon",
    "quality": 2,
    "sell_price_min": 6388,
    "sell_price_min_date": "2026-09-10T00:30:00",
    "sell_price_max": 6486,
    "sell_price_max_date": "2026-09-10T00:30:00",
    "buy_price_min": 0,
    "buy_price_min_date": "0001-01-01T00:00:00",
    "buy_price_max": 0,
    "buy_price_max_date": "0001-01-01T00:00:00",
}


class TestTimestamps:
    def test_timestamp_sem_fuso_e_utc(self):
        """Deixar o driver adivinhar o fuso desloca o preço em horas."""
        naive = datetime(2026, 9, 10, 0, 30)
        assert to_utc(naive) == datetime(2026, 9, 10, 0, 30, tzinfo=UTC)

    def test_sentinela_reconhecida(self):
        assert is_sentinel_date(datetime(1, 1, 1)) is True
        assert is_sentinel_date(datetime(2026, 9, 10)) is False


class TestNormalizePrice:
    def test_preco_valido_passa_com_fuso(self):
        value, date = normalize_price(6388, datetime(2026, 9, 10, 0, 30))
        assert value == 6388
        assert date == datetime(2026, 9, 10, 0, 30, tzinfo=UTC)

    def test_sentinela_vira_none_e_nao_zero(self):
        """Requisito 52. Zero produziria margem infinita na arbitragem."""
        assert normalize_price(0, datetime(1, 1, 1)) == (None, None)

    def test_preco_positivo_com_data_sentinela_e_descartado(self):
        """Cotação sem data não serve para decidir nada."""
        assert normalize_price(5000, datetime(1, 1, 1)) == (None, None)

    def test_preco_negativo_e_descartado(self):
        assert normalize_price(-1, datetime(2026, 9, 10)) == (None, None)


class TestNormalizePriceRow:
    def _normalize(self, raw: dict):
        return normalize_price_row(
            AodpPriceRow.model_validate(raw), 1, LOCATIONS, ITEMS, source_id=1,
            observed_at=OBSERVED,
        )

    def test_linha_real_com_venda_e_sem_compra(self):
        record = self._normalize(REAL_PRICE_ROW)
        assert isinstance(record, MarketPriceRecord)
        assert record.sell_price_min == 6388
        assert record.sell_price_min_date == datetime(2026, 9, 10, 0, 30, tzinfo=UTC)
        assert record.buy_price_max is None
        assert record.buy_price_max_date is None
        assert record.has_any_price is True

    def test_buy_e_sell_nao_se_misturam(self):
        """Requisito 13: trocar os dois inverte o sinal do lucro."""
        raw = REAL_PRICE_ROW | {
            "buy_price_max": 5000,
            "buy_price_max_date": "2026-09-12T10:00:00",
        }
        record = self._normalize(raw)
        assert isinstance(record, MarketPriceRecord)
        assert record.sell_price_min == 6388
        assert record.buy_price_max == 5000

    def test_cada_campo_tem_a_propria_idade(self):
        raw = REAL_PRICE_ROW | {
            "buy_price_max": 5000,
            "buy_price_max_date": "2026-09-01T10:00:00",
        }
        record = self._normalize(raw)
        assert isinstance(record, MarketPriceRecord)
        assert record.sell_price_min_date.day == 10
        assert record.buy_price_max_date.day == 1

    def test_linha_sem_nenhum_preco_e_marcada(self):
        raw = REAL_PRICE_ROW | {
            "sell_price_min": 0, "sell_price_min_date": "0001-01-01T00:00:00",
            "sell_price_max": 0, "sell_price_max_date": "0001-01-01T00:00:00",
        }
        record = self._normalize(raw)
        assert isinstance(record, MarketPriceRecord)
        assert record.has_any_price is False

    def test_local_desconhecido_e_rejeitado_com_motivo(self):
        """Uma portal city nova não pode virar linha órfã nem sumir em silêncio."""
        rejected = self._normalize(REAL_PRICE_ROW | {"city": "Thetford Portal"})
        assert isinstance(rejected, RejectedRow)
        assert rejected.reason == "local desconhecido"
        assert rejected.detail == "Thetford Portal"

    def test_item_fora_do_catalogo_e_rejeitado(self):
        rejected = self._normalize(REAL_PRICE_ROW | {"item_id": "T9_NOVIDADE"})
        assert isinstance(rejected, RejectedRow)
        assert rejected.reason == "item fora do catálogo"

    def test_qualidade_invalida_e_rejeitada(self):
        rejected = self._normalize(REAL_PRICE_ROW | {"quality": 0})
        assert isinstance(rejected, RejectedRow)
        assert rejected.reason == "qualidade fora da faixa"

    def test_black_market_e_normalizado_como_qualquer_local(self):
        record = self._normalize(REAL_PRICE_ROW | {"city": "Black Market"})
        assert isinstance(record, MarketPriceRecord)
        assert record.location_id == 3


class TestNormalizeHistory:
    def test_serie_real_vira_buckets(self):
        series = AodpHistorySeries.model_validate(
            {
                "location": "Black Market",
                "item_id": "T4_BAG",
                "quality": 1,
                "data": [
                    {"item_count": 424, "avg_price": 4425, "timestamp": "2026-08-13T00:00:00"},
                    {"item_count": 908, "avg_price": 4668, "timestamp": "2026-08-14T00:00:00"},
                ],
            }
        )
        records, rejected = normalize_history_series(
            series, 1, 24, LOCATIONS, ITEMS, source_id=1, ingested_at=OBSERVED
        )

        assert rejected == []
        assert len(records) == 2
        assert records[0].timescale == 24
        assert records[0].bucket_ts == datetime(2026, 8, 13, tzinfo=UTC)
        assert records[0].avg_price == 4425

    def test_ponto_invalido_e_rejeitado_sem_derrubar_a_serie(self):
        series = AodpHistorySeries.model_validate(
            {
                "location": "Caerleon",
                "item_id": "T4_BAG",
                "quality": 2,
                "data": [
                    {"item_count": 10, "avg_price": 0, "timestamp": "2026-08-13T00:00:00"},
                    {"item_count": 10, "avg_price": 4000, "timestamp": "2026-08-14T00:00:00"},
                ],
            }
        )
        records, rejected = normalize_history_series(
            series, 1, 24, LOCATIONS, ITEMS, source_id=1, ingested_at=OBSERVED
        )

        assert len(records) == 1
        assert len(rejected) == 1

    def test_outlier_nao_e_apagado_na_normalizacao(self):
        """29.790 entre 3.6k e 3.7k é real e suspeito.

        Descartar aqui esconderia informação: o valor cru é gravado e a marcação
        de outlier acontece depois, com a janela inteira à vista (fase 5).
        """
        series = AodpHistorySeries.model_validate(
            {
                "location": "Caerleon",
                "item_id": "T4_BAG",
                "quality": 2,
                "data": [
                    {"item_count": 1808, "avg_price": 29790, "timestamp": "2026-08-16T00:00:00"}
                ],
            }
        )
        records, _ = normalize_history_series(
            series, 1, 24, LOCATIONS, ITEMS, source_id=1, ingested_at=OBSERVED
        )
        assert records[0].avg_price == 29790


class TestNormalizeGold:
    def test_ponto_real(self):
        record = normalize_gold_point(
            AodpGoldPoint.model_validate({"price": 8000, "timestamp": "2026-09-12T21:00:00"}),
            server_id=1,
            source_id=1,
        )
        assert isinstance(record, GoldPriceRecord)
        assert record.price == 8000
        assert record.ts == datetime(2026, 9, 12, 21, 0, tzinfo=UTC)

    def test_servidor_vem_do_collector_e_nao_do_payload(self):
        """O endpoint de gold não informa servidor: quem sabe é o host chamado."""
        record = normalize_gold_point(
            AodpGoldPoint.model_validate({"price": 8000, "timestamp": "2026-09-12T21:00:00"}),
            server_id=3,
            source_id=1,
        )
        assert isinstance(record, GoldPriceRecord)
        assert record.server_id == 3

    @pytest.mark.parametrize("price", [0, -5])
    def test_preco_invalido_rejeitado(self, price):
        assert isinstance(
            normalize_gold_point(
                AodpGoldPoint.model_validate({"price": price, "timestamp": "2026-09-12T21:00:00"}),
                1,
                1,
            ),
            RejectedRow,
        )
