"""CLI de importação do catálogo.

    python -m app.cli.import_items
    python -m app.cli.import_items --names-file /tmp/items.json --metadata-file /tmp/items_full.json

Roda separado das migrations de propósito: são ~40 MB de download e o schema não
pode depender de rede para subir.
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.catalog.importer import DEFAULT_TRACKED_SUBCATEGORIES, import_catalog
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, init_engine


async def _main(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)

    engine = init_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    tracked = (
        frozenset(code.strip() for code in args.tracked.split(",") if code.strip())
        if args.tracked
        else DEFAULT_TRACKED_SUBCATEGORIES
    )

    try:
        async with session_factory() as session:
            report = await import_catalog(
                session,
                names_path=Path(args.names_file) if args.names_file else None,
                metadata_path=Path(args.metadata_file) if args.metadata_file else None,
                tracked_subcategories=tracked,
                apply_tracking=args.apply_tracking,
            )
    finally:
        await dispose_engine()

    width = max(len(key) for key in report.as_dict())
    for key, value in report.as_dict().items():
        print(f"{key.ljust(width)}  {value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa o catálogo de itens do ao-bin-dumps.")
    parser.add_argument("--names-file", help="caminho local de formatted/items.json")
    parser.add_argument("--metadata-file", help="caminho local de items.json (raiz do dump)")
    parser.add_argument(
        "--apply-tracking",
        action="store_true",
        help=(
            "reaplica is_tracked a partir da lista de subcategorias. "
            "Sem esta flag, a marcação existente no banco é preservada."
        ),
    )
    parser.add_argument(
        "--tracked",
        help=(
            "subcategorias marcadas para coleta, separadas por vírgula. "
            f"Padrão: {','.join(sorted(DEFAULT_TRACKED_SUBCATEGORIES))}"
        ),
    )
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
