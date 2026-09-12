"""Contrato das respostas do AODP.

Schemas estritos de propósito: se o AODP mudar o formato, a validação falha alto
e o payload cru fica em `raw_responses` para diagnóstico (risco R8). O que não
pode acontecer é o parser aceitar silenciosamente uma resposta diferente e
gravar dado errado.

Formatos verificados em 2026-09-12 contra respostas reais -- ver docs/02-aodp.md.
Atenção à inconsistência da API: o endpoint de preços chama o campo de `city`,
o de histórico chama de `location`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AodpPriceRow(BaseModel):
    """Linha de /api/v2/stats/prices."""

    model_config = ConfigDict(extra="ignore")

    item_id: str
    city: str
    quality: int
    sell_price_min: int
    sell_price_min_date: datetime
    sell_price_max: int
    sell_price_max_date: datetime
    buy_price_min: int
    buy_price_min_date: datetime
    buy_price_max: int
    buy_price_max_date: datetime


class AodpHistoryPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_count: int
    avg_price: int
    timestamp: datetime


class AodpHistorySeries(BaseModel):
    """Série de /api/v2/stats/history. Aninhada, ao contrário do endpoint de preços."""

    model_config = ConfigDict(extra="ignore")

    location: str
    item_id: str
    quality: int
    data: list[AodpHistoryPoint] = Field(default_factory=list)


class AodpGoldPoint(BaseModel):
    """Ponto de /api/v2/stats/gold.

    Sem campo de servidor: o servidor é o host chamado, e quem sabe disso é o
    collector.
    """

    model_config = ConfigDict(extra="ignore")

    price: int
    timestamp: datetime
