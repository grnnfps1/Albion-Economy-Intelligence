"""CLI do collector de mercado.

    python -m app.cli.collect_market --server west
    python -m app.cli.collect_market --server west --loop --interval 600

Com `--loop` o processo fica vivo e repete. É assim que ele roda em produção --
num container long-running, nunca em função serverless: o collector mantém
estado (cursor, janela de rate limit, backoff) e um ambiente que mata o processo
no meio produz coleta parcial e estouro de cota.
"""

import argparse
import asyncio
import signal

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache.locks import LockNotAcquired
from app.cache.redis import close_redis, init_redis
from app.collectors.market_collector import collect_market_prices
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, init_engine

log = get_logger(__name__)


async def _run_once(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = init_engine(settings)
    redis = init_redis(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    stop = asyncio.Event()

    def _request_stop(*_args: object) -> None:
        log.info("sinal recebido; encerrando depois do ciclo atual")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with __import__("contextlib").suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    exit_code = 0
    try:
        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            while True:
                try:
                    result = await collect_market_prices(
                        settings,
                        session_factory,
                        redis,
                        args.server,
                        http_client,
                        qualities=[int(q) for q in args.qualities.split(",")]
                        if args.qualities
                        else None,
                        store_raw=not args.no_raw,
                    )
                    for key, value in result.as_dict().items():
                        print(f"{key:<20} {value}")
                    if result.status == "failed":
                        exit_code = 1
                except LockNotAcquired as exc:
                    # Não é erro: é outro processo fazendo o trabalho.
                    log.info("coleta ignorada", reason=str(exc))

                if not args.loop or stop.is_set():
                    break

                log.info("aguardando proximo ciclo", interval_seconds=args.interval)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=args.interval)
                    break
                except TimeoutError:
                    continue
    finally:
        await close_redis()
        await dispose_engine()

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta preços de mercado do AODP.")
    parser.add_argument("--server", default="west", help="west | east | europe")
    parser.add_argument("--qualities", help="qualidades separadas por vírgula, ex.: 1,2")
    parser.add_argument("--loop", action="store_true", help="repete indefinidamente")
    parser.add_argument(
        "--interval", type=int, default=900, help="segundos entre ciclos com --loop"
    )
    parser.add_argument(
        "--no-raw", action="store_true", help="não gravar payloads em raw_responses"
    )
    args = parser.parse_args()

    configure_logging(get_settings())
    return asyncio.run(_run_once(args))


if __name__ == "__main__":
    raise SystemExit(main())
