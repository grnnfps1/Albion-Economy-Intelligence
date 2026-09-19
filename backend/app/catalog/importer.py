"""Importação do catálogo de itens a partir do dump oficial do cliente.

Duas fontes, com papéis diferentes:

1. `formatted/items.json` — lista canônica de identificadores, **incluindo as
   variantes encantadas** (`T4_BAG@1`, `T4_PLANKS_LEVEL1@1`). É esta lista que
   define o que existe, porque é exatamente o vocabulário que o AODP usa.
   Traz os nomes localizados.

2. `items.json` (raiz do repositório) — metadados: tier, peso, categoria de
   loja, qualidade máxima e receitas. Só contém itens **base**; as variantes
   encantadas ficam aninhadas. Por isso a resolução de qual entrada do dump
   corresponde a cada identificador passa pelo parser.

Campo sem informação vira NULL. Nada é inferido (requisito 52).
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.parser import InvalidItemName, parse_item_name, resolve_base_name
from app.core.logging import get_logger
from app.models.catalog import Item
from app.models.reference import ItemCategory

log = get_logger(__name__)

DUMPS_BASE = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master"
NAMES_URL = f"{DUMPS_BASE}/formatted/items.json"
METADATA_URL = f"{DUMPS_BASE}/items.json"

# Itens que a coleta varre por padrão. Varrer 12 mil identificadores a 1 req/s
# não fecha a conta (risco R5), então a coleta começa pelo que tem liquidez e
# interessa a refino/crafting.
#
# Estes códigos são os valores reais de `@shopsubcategory1` no dump, conferidos
# contra o banco depois da primeira importação. A intuição erra aqui: recurso
# bruto é `resources`, não `rawresources`.
# `farm`, `herbgarden`, `pasture` e `kennel` entram porque a fase de agricultura
# precisa do preço da semente, do filhote e do adulto; `farmingproducts` é onde
# ficam carne, leite e ovo. São ~150 identificadores a mais — cabem no orçamento
# de 1 req/s. Sem eles a tela de agricultura calcula UNKNOWN por falta de preço.
DEFAULT_TRACKED_SUBCATEGORIES = frozenset(
    {
        "resources",
        "refinedresources",
        "cityresources",
        "tokens",
        "farm",
        "herbgarden",
        "pasture",
        "kennel",
        "farmingproducts",
    }
)


@dataclass
class ImportReport:
    names_loaded: int = 0
    metadata_entries: int = 0
    categories_upserted: int = 0
    items_upserted: int = 0
    items_without_metadata: int = 0
    items_without_tier: int = 0
    items_tracked: int = 0
    invalid_names: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


# --------------------------------------------------------------------------- #
# Leitura das fontes
# --------------------------------------------------------------------------- #


async def _fetch_json(url: str, timeout: float) -> Any:
    # Arquivos de dezenas de MB: streaming e timeout generoso.
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"Accept-Encoding": "gzip"})
        response.raise_for_status()
        return response.json()


async def load_sources(
    names_path: Path | None = None,
    metadata_path: Path | None = None,
    timeout: float = 120.0,
) -> tuple[list[dict], dict]:
    """Carrega as duas fontes, de disco quando informado, senão da rede.

    Poder apontar para arquivo local importa: torna o import reprodutível e
    permite rodar o teste sem rede.
    """
    if names_path is not None:
        names = json.loads(names_path.read_text(encoding="utf-8"))
    else:
        names = await _fetch_json(NAMES_URL, timeout)

    if metadata_path is not None:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = await _fetch_json(METADATA_URL, timeout)

    return names, metadata


def index_metadata(metadata: dict) -> dict[str, dict]:
    """Achata o dump completo em `uniquename -> entrada`.

    O dump é agrupado por tipo (`simpleitem`, `weapon`, `equipmentitem`, ...),
    e cada grupo pode ser lista ou objeto único.
    """
    root = metadata.get("items", metadata)
    index: dict[str, dict] = {}

    for group in root.values():
        entries: Iterable[Any]
        if isinstance(group, list):
            entries = group
        elif isinstance(group, dict):
            entries = [group]
        else:
            continue

        for entry in entries:
            if isinstance(entry, dict) and "@uniquename" in entry:
                index[entry["@uniquename"]] = entry

    return index


# --------------------------------------------------------------------------- #
# Normalização
# --------------------------------------------------------------------------- #


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class NormalizedItem:
    unique_name: str
    base_name: str
    tier: int | None
    enchantment: int
    category_code: str | None
    subcategory_code: str | None
    display_name_en: str | None
    display_name_pt: str | None
    weight: float | None
    max_quality: int | None
    # `@itemvalue`: base da nutrição consumida na estação. NULL quando o dump
    # não traz -- e aí a taxa da estação sai UNKNOWN, não zero.
    item_value: float | None
    # Ração. Só cultivo, carne e animal adulto têm; nos outros é NULL.
    nutrition: int | None
    food_category: str | None
    is_tracked: bool
    has_metadata: bool


def normalize(
    name_entry: dict,
    metadata_index: dict[str, dict],
    tracked_subcategories: frozenset[str] = DEFAULT_TRACKED_SUBCATEGORIES,
) -> NormalizedItem | None:
    """Converte uma entrada de `formatted/items.json` em linha de `items`."""
    unique_name = (name_entry.get("UniqueName") or "").strip()
    if not unique_name:
        return None

    try:
        parsed = parse_item_name(unique_name)
    except InvalidItemName:
        return None

    base_name = resolve_base_name(parsed, lambda key: key in metadata_index)
    meta = metadata_index.get(base_name, {})

    # `@itemvalue` é a exceção ao agrupamento por `base_name`, e a única até
    # agora. `resolve_base_name` prefere a raiz sem `_LEVELN` -- o que está
    # certo para peso, categoria e tier, idênticos entre as variantes --, mas o
    # valor do item **quadruplica** no encantamento 2: `T8_LEATHER` = 256 e
    # `T8_LEATHER_LEVEL2` = 1.024. Herdar a raiz faria a taxa da estação de todo
    # item encantado sair baixa, e errar para menos em taxa é inflar lucro.
    valor = metadata_index.get(parsed.literal_base, meta).get("@itemvalue")

    localized = name_entry.get("LocalizedNames") or {}
    subcategory = meta.get("@shopsubcategory1")

    # O tier do dump manda; o derivado do identificador é fallback. Ambos ausentes
    # significam NULL -- não existe "tier 1 por padrão".
    tier = _as_int(meta.get("@tier"))
    if tier is None:
        tier = parsed.tier

    return NormalizedItem(
        unique_name=unique_name,
        base_name=base_name,
        tier=tier,
        enchantment=parsed.enchantment,
        category_code=meta.get("@shopcategory"),
        subcategory_code=subcategory,
        display_name_en=localized.get("EN-US"),
        display_name_pt=localized.get("PT-BR"),
        weight=_as_float(meta.get("@weight")),
        max_quality=_as_int(meta.get("@maxqualitylevel")),
        item_value=_as_float(valor),
        nutrition=_as_int(meta.get("@nutrition")),
        food_category=meta.get("@foodcategory"),
        is_tracked=subcategory in tracked_subcategories,
        has_metadata=bool(meta),
    )


def _humanize(code: str) -> str:
    return code.replace("_", " ").replace("-", " ").strip().title()


# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #


async def _upsert_categories(session: AsyncSession, codes: set[str]) -> dict[str, int]:
    """Cria as categorias que o dump trouxe e devolve `code -> id`.

    As categorias não são inventadas aqui: são os valores de `@shopcategory` que
    apareceram no dump.
    """
    if codes:
        await session.execute(
            pg_insert(ItemCategory)
            .values([{"code": code, "display_name": _humanize(code)} for code in sorted(codes)])
            .on_conflict_do_nothing(index_elements=[ItemCategory.code]),
        )
        await session.flush()

    rows = await session.execute(select(ItemCategory.code, ItemCategory.id))
    return dict(rows.all())


async def _upsert_items(
    session: AsyncSession,
    items: list[NormalizedItem],
    category_ids: dict[str, int],
    apply_tracking: bool = False,
) -> int:
    """UPSERT por `unique_name`.

    Reimportar depois de um patch atualiza nome, peso e categoria sem recriar a
    linha -- as chaves estrangeiras de preço e histórico apontam para `items.id`
    e não podem mudar.

    `is_tracked` NÃO é sobrescrito por padrão: é decisão operacional de coleta,
    não metadado do jogo, e um reimport de rotina não pode desligar o que alguém
    ligou na mão. Quando a lista padrão muda e se quer reaplicá-la, passar
    `apply_tracking=True` explicitamente.
    """
    if not items:
        return 0

    payload = [
        {
            "unique_name": item.unique_name,
            "base_name": item.base_name,
            "tier": item.tier,
            "enchantment": item.enchantment,
            "category_id": category_ids.get(item.category_code) if item.category_code else None,
            "subcategory_code": item.subcategory_code,
            "display_name_en": item.display_name_en,
            "display_name_pt": item.display_name_pt,
            "weight": item.weight,
            "max_quality": item.max_quality,
            "item_value": item.item_value,
            "nutrition": item.nutrition,
            "food_category": item.food_category,
            "is_tracked": item.is_tracked,
            "active": True,
        }
        for item in items
    ]

    total = 0
    chunk_size = 1000
    for start in range(0, len(payload), chunk_size):
        chunk = payload[start : start + chunk_size]
        statement = pg_insert(Item).values(chunk)
        statement = statement.on_conflict_do_update(
            index_elements=[Item.unique_name],
            set_={
                "base_name": statement.excluded.base_name,
                "tier": statement.excluded.tier,
                "enchantment": statement.excluded.enchantment,
                "category_id": statement.excluded.category_id,
                "subcategory_code": statement.excluded.subcategory_code,
                "display_name_en": statement.excluded.display_name_en,
                "display_name_pt": statement.excluded.display_name_pt,
                "weight": statement.excluded.weight,
                "max_quality": statement.excluded.max_quality,
                "item_value": statement.excluded.item_value,
                "nutrition": statement.excluded.nutrition,
                "food_category": statement.excluded.food_category,
                "active": statement.excluded.active,
                **(
                    {"is_tracked": statement.excluded.is_tracked} if apply_tracking else {}
                ),
            },
        )
        await session.execute(statement)
        total += len(chunk)

    return total


async def import_catalog(
    session: AsyncSession,
    names_path: Path | None = None,
    metadata_path: Path | None = None,
    tracked_subcategories: frozenset[str] = DEFAULT_TRACKED_SUBCATEGORIES,
    apply_tracking: bool = False,
) -> ImportReport:
    report = ImportReport()

    names, metadata = await load_sources(names_path, metadata_path)
    metadata_index = index_metadata(metadata)
    report.names_loaded = len(names)
    report.metadata_entries = len(metadata_index)

    normalized: list[NormalizedItem] = []
    for entry in names:
        item = normalize(entry, metadata_index, tracked_subcategories)
        if item is None:
            report.invalid_names += 1
            continue
        normalized.append(item)
        if not item.has_metadata:
            report.items_without_metadata += 1
        if item.tier is None:
            report.items_without_tier += 1
        if item.is_tracked:
            report.items_tracked += 1

    category_codes = {item.category_code for item in normalized if item.category_code}
    category_ids = await _upsert_categories(session, category_codes)
    report.categories_upserted = len(category_ids)

    report.items_upserted = await _upsert_items(
        session, normalized, category_ids, apply_tracking=apply_tracking
    )
    await session.commit()

    log.info("catalogo importado", **report.as_dict())
    return report
