"""Importação e consulta do catálogo contra PostgreSQL de verdade."""

import pytest

from app.catalog.importer import import_catalog
from app.repositories import items as items_repo

pytestmark = pytest.mark.asyncio

def _name(unique_name: str, en: str | None = None, pt: str | None = None) -> dict:
    localized = {}
    if en:
        localized["EN-US"] = en
    if pt:
        localized["PT-BR"] = pt
    return {"UniqueName": unique_name, "LocalizedNames": localized}


NAMES = [
    _name("T4_PLANKS", "Pine Planks", "Tábuas de Pinho"),
    _name("T4_PLANKS_LEVEL1@1", pt="Tábuas de Pinho Incomuns"),
    _name("T5_LEATHER", "Cured Leather", "Couro Curtido"),
    _name("T4_BAG@1", "Adept's Bag"),
    _name("UNIQUE_HIDEOUT", "Hideout Construction Kit"),
]

METADATA = {
    "items": {
        "simpleitem": [
            {
                "@uniquename": "T4_PLANKS",
                "@tier": "4",
                "@weight": "0.51",
                "@shopcategory": "crafting",
                "@shopsubcategory1": "refinedresources",
            },
            {
                "@uniquename": "T5_LEATHER",
                "@tier": "5",
                "@weight": "0.61",
                "@shopcategory": "crafting",
                "@shopsubcategory1": "refinedresources",
            },
        ],
        "equipmentitem": [
            {
                "@uniquename": "T4_BAG",
                "@tier": "4",
                "@weight": "1.5",
                "@maxqualitylevel": "5",
                "@shopcategory": "bags",
                "@shopsubcategory1": "bag",
            }
        ],
    }
}


async def _import(session, tmp_path, **kwargs):
    import json

    names_path = tmp_path / "names.json"
    metadata_path = tmp_path / "metadata.json"
    names_path.write_text(json.dumps(NAMES), encoding="utf-8")
    metadata_path.write_text(json.dumps(METADATA), encoding="utf-8")
    return await import_catalog(session, names_path, metadata_path, **kwargs)


async def test_import_grava_catalogo_completo(session, tmp_path):
    report = await _import(session, tmp_path)

    assert report.names_loaded == 5
    assert report.items_upserted == 5
    assert report.invalid_names == 0
    # UNIQUE_HIDEOUT e T4_PLANKS_LEVEL1@1 -> o primeiro sem metadado, o segundo herda de T4_PLANKS
    assert report.items_without_metadata == 1

    item = await items_repo.get_by_unique_name(session, "T4_PLANKS_LEVEL1@1")
    assert item is not None
    assert item.base_name == "T4_PLANKS"
    assert item.enchantment == 1
    assert item.tier == 4
    assert float(item.weight) == 0.51


async def test_import_e_idempotente(session, tmp_path):
    await _import(session, tmp_path)
    counts_first = await items_repo.count_items(session)

    await _import(session, tmp_path)
    counts_second = await items_repo.count_items(session)

    assert counts_first == counts_second


async def test_reimport_preserva_is_tracked_por_padrao(session, tmp_path):
    await _import(session, tmp_path, tracked_subcategories=frozenset({"refinedresources"}))
    assert (await items_repo.count_items(session))["tracked"] == 3

    # Lista de rastreio vazia: sem a flag, o que já estava marcado continua marcado.
    await _import(session, tmp_path, tracked_subcategories=frozenset())
    assert (await items_repo.count_items(session))["tracked"] == 3

    # Com a flag, a nova lista é aplicada.
    await _import(session, tmp_path, tracked_subcategories=frozenset(), apply_tracking=True)
    assert (await items_repo.count_items(session))["tracked"] == 0


async def test_busca_por_nome_visual_e_por_id_tecnico(session, tmp_path):
    await _import(session, tmp_path)

    por_nome, total_nome = await items_repo.search_items(session, search="couro")
    por_id, total_id = await items_repo.search_items(session, search="T5_LEATHER")

    assert total_nome == 1
    assert total_id == 1
    assert por_nome[0].unique_name == por_id[0].unique_name == "T5_LEATHER"


async def test_filtro_por_tier_e_encantamento(session, tmp_path):
    await _import(session, tmp_path)

    _, total_t4 = await items_repo.search_items(session, tier=4)
    _, total_e1 = await items_repo.search_items(session, enchantment=1)

    assert total_t4 == 3           # T4_PLANKS, T4_PLANKS_LEVEL1@1, T4_BAG@1
    assert total_e1 == 2           # T4_PLANKS_LEVEL1@1, T4_BAG@1


async def test_paginacao_devolve_total_real(session, tmp_path):
    await _import(session, tmp_path)

    page, total = await items_repo.search_items(session, limit=2, offset=0)

    assert len(page) == 2
    assert total == 5


async def test_item_sem_tier_nao_e_perdido_na_ordenacao(session, tmp_path):
    """Ordenar por tier com NULL não pode esconder o item da listagem."""
    await _import(session, tmp_path)
    page, total = await items_repo.search_items(session, limit=100)

    assert total == 5
    assert "UNIQUE_HIDEOUT" in {item.unique_name for item in page}
    assert page[-1].unique_name == "UNIQUE_HIDEOUT"  # NULLS LAST
