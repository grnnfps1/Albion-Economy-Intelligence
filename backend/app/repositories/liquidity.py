"""Sinais de liquidez derivados do histórico.

O endpoint de histórico do AODP devolve `item_count` por bucket: quantas
unidades foram negociadas naquele intervalo. É a única medida de volume que a
fonte oferece, e é o que separa "margem enorme em item que ninguém compra" de
"oportunidade de verdade" (requisito 21).

Dois sinais, com papéis diferentes:

- `units_per_day`   — quanto gira. Responde "dá para escoar?".
- `days_with_data`  — em quantos dos últimos N dias existe registro. Responde
                      "eu confio nesse número?". Um item com cotação de hoje mas
                      só 3 dias de histórico em 30 tem preço frágil, mesmo fresco.

Sem histórico suficiente, o resultado é UNKNOWN. Não se inventa liquidez.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import MarketHistory
from app.models.reference import Server

# Abaixo disto, a amostra é pequena demais para dizer qualquer coisa.
MIN_BUCKETS = 3


@dataclass(frozen=True)
class LiquiditySignal:
    units_per_day: float | None
    days_with_data: int
    period_days: int
    median_price: float | None

    @property
    def known(self) -> bool:
        return self.units_per_day is not None


async def liquidity_by_item_location(
    session: AsyncSession,
    server_code: str,
    item_ids: list[int],
    period_days: int = 30,
    timescale: int = 24,
) -> dict[tuple[int, int, int], LiquiditySignal]:
    """Agrega por (item_id, location_id, quality).

    Uma consulta só para a página inteira: uma por linha traria o problema
    clássico de N+1 numa tabela que cresce sem parar.

    Buckets marcados como outlier ficam de fora — tanto do volume quanto da
    mediana. Um pico de preço manipulado costuma vir acompanhado de volume
    igualmente irreal.
    """
    if not item_ids:
        return {}

    since = datetime.now(UTC) - timedelta(days=period_days)

    rows = await session.execute(
        select(
            MarketHistory.item_id,
            MarketHistory.location_id,
            MarketHistory.quality,
            func.sum(MarketHistory.item_count),
            func.count(MarketHistory.bucket_ts),
            func.percentile_cont(0.5)
            .within_group(MarketHistory.avg_price)
            .label("median_price"),
        )
        .join(Server, MarketHistory.server_id == Server.id)
        .where(
            Server.code == server_code,
            MarketHistory.item_id.in_(item_ids),
            MarketHistory.timescale == timescale,
            MarketHistory.bucket_ts >= since,
            MarketHistory.is_outlier.is_(False),
        )
        .group_by(
            MarketHistory.item_id, MarketHistory.location_id, MarketHistory.quality
        )
    )

    signals: dict[tuple[int, int, int], LiquiditySignal] = {}
    for item_id, location_id, quality, total_units, buckets, median_price in rows.all():
        if buckets < MIN_BUCKETS:
            signals[(item_id, location_id, quality)] = LiquiditySignal(
                None, int(buckets), period_days, None
            )
            continue

        # Divide pelos dias observados, não pelos dias do período: um item que
        # só aparece em 5 dias gira o que gira nesses 5, e dividir por 30
        # esconderia o giro real.
        horas = timescale * buckets
        dias_observados = max(horas / 24, 1)
        signals[(item_id, location_id, quality)] = LiquiditySignal(
            units_per_day=round(float(total_units) / dias_observados, 1),
            days_with_data=int(buckets * timescale / 24) or int(buckets),
            period_days=period_days,
            median_price=float(median_price) if median_price is not None else None,
        )

    return signals
