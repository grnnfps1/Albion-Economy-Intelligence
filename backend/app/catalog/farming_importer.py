"""Importação de agricultura e criação a partir do dump oficial.

Duas fontes, porque o dump separa o que é plantado do que é colhido:

- `items.json` → `farmableitem`: 8 de fazenda, 7 de horta, 42 de pasto e 52 de
  canil. Traz o tempo, o custo em Focus e a ração.
- `loot.json` → `LootDefinition.Lootlist`: traz **o que a colheita entrega**.
  `harvest.@lootlist` é só o nome da lista (`T1_CARROT_LOOT`); sem resolver, não
  se sabe nem qual item sai nem quantos.

Três irregularidades do dump que precisam de tratamento, não de suposição:

- `Item` dentro de uma lista de loot pode ser **objeto ou lista**, como
  `craftingrequirements` em receitas.
- `@amount` é **faixa**: `"3-6"`, não `"4"`. A faixa é preservada nas duas
  colunas; achatar aqui apagaria a incerteza antes de alguém poder vê-la.
- Nem todo item da lista de loot é o cultivo: `T1_CARROT_LOOT` traz a cenoura
  com chance 1.0 **e** uma minhoca com chance 0.1.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.catalog import Item
from app.models.farming import Farmable, FarmableOutput

log = get_logger(__name__)

DUMPS_BASE = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master"
LOOT_URL = f"{DUMPS_BASE}/loot.json"

# `@shopsubcategory2` → papel no ciclo.
ROLE_BY_SUBCATEGORY = {"seeds": "seed", "babys": "baby", "animals": "grown"}

STATIONS = frozenset({"farm", "herbgarden", "pasture", "kennel"})


@dataclass
class FarmingImportReport:
    farmables_seen: int = 0
    farmables_upserted: int = 0
    outputs_upserted: int = 0
    items_missing_from_catalog: int = 0
    loot_lists_missing: int = 0
    without_outputs: int = 0
    missing_examples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "missing_examples"}


# --------------------------------------------------------------------------- #
# Leitura das fontes
# --------------------------------------------------------------------------- #


async def load_loot(path: Path | None = None) -> dict[str, dict]:
    """`nome da lista -> definição`, do arquivo local ou do dump."""
    if path is not None:
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            response = await client.get(LOOT_URL)
            response.raise_for_status()
            raw = response.json()

    listas = raw.get("LootDefinition", raw).get("Lootlist", [])
    if isinstance(listas, dict):
        listas = [listas]
    return {
        entry["@name"]: entry
        for entry in listas
        if isinstance(entry, dict) and "@name" in entry
    }


def _as_list(value: Any) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_amount(value: Any) -> tuple[int, int]:
    """`"3-6"` vira `(3, 6)`; `"1"` vira `(1, 1)`.

    Faixa é a forma como o dump expressa a incerteza da colheita. Devolver só a
    média aqui transformaria "entre 3 e 6" em "4.5" cedo demais, e ninguém mais
    veria que havia uma faixa.
    """
    texto = str(value or "1").strip()
    if "-" in texto:
        low, _, high = texto.partition("-")
        inicio, fim = _as_int(low), _as_int(high)
        if inicio is not None and fim is not None and fim >= inicio:
            return inicio, fim
    unico = _as_int(texto)
    return (unico, unico) if unico is not None else (1, 1)


def loot_entries(lista: dict | None) -> list[tuple[str, int, int, float]]:
    """`(unique_name, amount_min, amount_max, chance)` de uma lista de loot."""
    if not lista:
        return []
    saida = []
    for entrada in _as_list(lista.get("Item")):
        nome = entrada.get("@type")
        if not nome:
            continue
        minimo, maximo = parse_amount(entrada.get("@amount"))
        saida.append((nome, minimo, maximo, _as_float(entrada.get("@chance")) or 0.0))
    return saida


# --------------------------------------------------------------------------- #
# Normalização
# --------------------------------------------------------------------------- #


@dataclass
class NormalizedOutput:
    unique_name: str
    role: str
    amount_min: int
    amount_max: int
    chance: float


@dataclass
class NormalizedFarmable:
    unique_name: str
    station: str
    role: str
    cycle_seconds: int | None
    grow_seconds: int | None
    product_seconds: int | None
    focus_cost: int | None
    max_cycles: int | None
    active_farm_bonus: float | None
    npc_silver_cost: int | None
    grown_unique_name: str | None
    accepted_food_category: str | None
    seconds_per_nutrition: float | None
    nutrition_max: int | None
    favorite_food: str | None
    outputs: list[NormalizedOutput]


def normalize(entry: dict, loot: dict[str, dict]) -> NormalizedFarmable | None:
    """Uma entrada de `farmableitem` vira uma linha de `farmables` e suas saídas."""
    unique_name = entry.get("@uniquename")
    station = entry.get("@shopsubcategory1")
    role = ROLE_BY_SUBCATEGORY.get(entry.get("@shopsubcategory2") or "")
    if not unique_name or station not in STATIONS or role is None:
        return None

    saidas: list[NormalizedOutput] = []
    grow_seconds = None
    product_seconds = None

    colheita = entry.get("harvest")
    if isinstance(colheita, dict):
        grow_seconds = _as_int(colheita.get("@growtime"))
        chance_lista = _as_float(colheita.get("@lootchance"))
        chance_lista = 1.0 if chance_lista is None else chance_lista
        for nome, minimo, maximo, chance in loot_entries(loot.get(colheita.get("@lootlist"))):
            saidas.append(NormalizedOutput(nome, "harvest", minimo, maximo, chance * chance_lista))
        semente = colheita.get("seed")
        if isinstance(semente, dict):
            minimo, maximo = parse_amount(semente.get("@amount"))
            # A semente que volta é a própria semente plantada.
            saidas.append(
                NormalizedOutput(
                    unique_name, "seed_return", minimo, maximo,
                    _as_float(semente.get("@chance")) or 0.0,
                )
            )

    adulto = entry.get("grownitem")
    grown_unique_name = None
    if isinstance(adulto, dict):
        grown_unique_name = adulto.get("@uniquename")
        grow_seconds = _as_int(adulto.get("@growtime"))
        if grown_unique_name:
            saidas.append(NormalizedOutput(grown_unique_name, "grown", 1, 1, 1.0))
        cria = adulto.get("offspring")
        if isinstance(cria, dict):
            minimo, maximo = parse_amount(cria.get("@amount"))
            # A cria é outro filhote igual ao que foi colocado no pasto.
            saidas.append(
                NormalizedOutput(
                    unique_name, "offspring", minimo, maximo,
                    _as_float(cria.get("@chance")) or 0.0,
                )
            )

    produtos = entry.get("products")
    if isinstance(produtos, dict):
        for produto in _as_list(produtos.get("product")):
            product_seconds = _as_int(produto.get("@productiontime"))
            chance_lista = _as_float(produto.get("@lootchance"))
            chance_lista = 1.0 if chance_lista is None else chance_lista
            for nome, minimo, maximo, chance in loot_entries(loot.get(produto.get("@lootlist"))):
                saidas.append(
                    NormalizedOutput(nome, "product", minimo, maximo, chance * chance_lista)
                )

    comida = (entry.get("consumption") or {}).get("food") if isinstance(
        entry.get("consumption"), dict
    ) else None
    aceita = (comida or {}).get("acceptedfood") or {}

    receita = _as_list(entry.get("craftingrequirements"))

    return NormalizedFarmable(
        unique_name=unique_name,
        station=station,
        role=role,
        cycle_seconds=_as_int(entry.get("@activefarmcyclelengthseconds")),
        grow_seconds=grow_seconds,
        product_seconds=product_seconds,
        focus_cost=_as_int(entry.get("@activefarmfocuscost")),
        max_cycles=_as_int(entry.get("@activefarmmaxcycles")),
        active_farm_bonus=_as_float(entry.get("@activefarmbonus")),
        npc_silver_cost=_as_int(receita[0].get("@silver")) if receita else None,
        grown_unique_name=grown_unique_name,
        accepted_food_category=aceita.get("@foodcategory") if isinstance(aceita, dict) else None,
        seconds_per_nutrition=_as_float((comida or {}).get("@secondspernutrition")),
        nutrition_max=_as_int((comida or {}).get("@nutritionmax")),
        favorite_food=aceita.get("@favorite") if isinstance(aceita, dict) else None,
        outputs=saidas,
    )


def iter_farmables(metadata: dict) -> Iterable[dict]:
    root = metadata.get("items", metadata)
    grupo = root.get("farmableitem", [])
    return grupo if isinstance(grupo, list) else [grupo]


# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #


async def import_farmables(
    session: AsyncSession, metadata: dict, loot: dict[str, dict]
) -> FarmingImportReport:
    """Regrava `farmables` e `farmable_outputs` a partir do dump.

    Reescreve em vez de fazer merge: o dump é a verdade sobre o jogo e uma linha
    que sumiu dele não deve sobreviver no banco. `items` não é tocado -- as
    chaves de preço apontam para `items.id` e não podem mudar.
    """
    report = FarmingImportReport()

    normalizados = [
        normalizado
        for entrada in iter_farmables(metadata)
        if isinstance(entrada, dict)
        for normalizado in [normalize(entrada, loot)]
        if normalizado is not None
    ]
    report.farmables_seen = len(normalizados)
    if not normalizados:
        return report

    nomes = {n.unique_name for n in normalizados}
    for n in normalizados:
        nomes.update(o.unique_name for o in n.outputs)
        if n.grown_unique_name:
            nomes.add(n.grown_unique_name)
        if n.favorite_food:
            nomes.add(n.favorite_food)

    rows = await session.execute(
        select(Item.unique_name, Item.id).where(Item.unique_name.in_(sorted(nomes)))
    )
    catalogo = dict(rows.all())

    await session.execute(delete(FarmableOutput))
    await session.execute(delete(Farmable))
    await session.flush()

    for normalizado in normalizados:
        item_id = catalogo.get(normalizado.unique_name)
        if item_id is None:
            report.items_missing_from_catalog += 1
            if len(report.missing_examples) < 10:
                report.missing_examples.append(normalizado.unique_name)
            continue

        farmable = Farmable(
            item_id=item_id,
            station=normalizado.station,
            role=normalizado.role,
            cycle_seconds=normalizado.cycle_seconds,
            grow_seconds=normalizado.grow_seconds,
            product_seconds=normalizado.product_seconds,
            focus_cost=normalizado.focus_cost,
            max_cycles=normalizado.max_cycles,
            active_farm_bonus=normalizado.active_farm_bonus,
            npc_silver_cost=normalizado.npc_silver_cost,
            grown_item_id=catalogo.get(normalizado.grown_unique_name or ""),
            accepted_food_category=normalizado.accepted_food_category,
            seconds_per_nutrition=normalizado.seconds_per_nutrition,
            nutrition_max=normalizado.nutrition_max,
            favorite_food_item_id=catalogo.get(normalizado.favorite_food or ""),
        )
        session.add(farmable)
        await session.flush()
        report.farmables_upserted += 1

        vistos: set[tuple[int, str]] = set()
        for saida in normalizado.outputs:
            saida_id = catalogo.get(saida.unique_name)
            if saida_id is None:
                report.items_missing_from_catalog += 1
                if len(report.missing_examples) < 10:
                    report.missing_examples.append(saida.unique_name)
                continue
            chave = (saida_id, saida.role)
            if chave in vistos:
                continue
            vistos.add(chave)
            session.add(
                FarmableOutput(
                    farmable_id=farmable.id,
                    item_id=saida_id,
                    role=saida.role,
                    amount_min=saida.amount_min,
                    amount_max=saida.amount_max,
                    chance=min(1.0, max(0.0, saida.chance)),
                )
            )
            report.outputs_upserted += 1

        if not vistos:
            report.without_outputs += 1

    await session.commit()
    log.info("farmables_importados", **report.as_dict())
    return report
