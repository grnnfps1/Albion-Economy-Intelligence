"""CLI dos collectors de histórico e gold.

    python -m app.cli.collect_history --server west --timescale 24 --days 30
    python -m app.cli.collect_history --server west --gold

Frequência baixa de propósito: o bucket é de hora ou de dia, e recoletar de
minuto em minuto gasta cota sem gerar informação nova.
"""

import argparse
import asyncio

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache.locks import LockNotAcquired
from app.cache.redis import close_redis, init_redis
from app.collectors.history_collector import collect_gold, collect_history
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, init_engine

log = get_logger(__name__)


async def _main(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = init_engine(settings)
    redis = init_redis(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            if args.gold:
                saved = await collect_gold(settings, factory, redis, args.server, http_client)
                print(f"gold: {saved} pontos")
                return 0

            result = await collect_history(
                settings, factory, redis, args.server, http_client,
                timescale=args.timescale, days=args.days,
            )
            for key, value in result.as_dict().items():
                print(f"{key:<20} {value}")
            return 1 if result.status == "failed" else 0
    except LockNotAcquired as exc:
        log.info("coleta ignorada", reason=str(exc))
        return 0
    finally:
        await close_redis()
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta histórico e gold do AODP.")
    parser.add_argument("--server", default="west")
    parser.add_argument("--timescale", type=int, default=24, choices=[1, 6, 24])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--gold", action="store_true", help="coleta cotação de gold")
    args = parser.parse_args()
    configure_logging(get_settings())
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
