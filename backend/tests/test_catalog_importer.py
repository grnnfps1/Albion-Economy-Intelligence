"""Normalização do catálogo.

Fixtures pequenas com a forma real do dump. Sem rede (requisito 43).
"""

from app.catalog.importer import index_metadata, normalize

# Recorte fiel de items.json (raiz do dump): agrupado por tipo, chaves com '@'.
METADATA = {
    "items": {
        "shopcategories": {"ignorado": True},
        "simpleitem": [
            {
                "@uniquename": "T4_PLANKS",
                "@tier": "4",
                "@weight": "0.51",
                "@shopcategory": "crafting",
                "@shopsubcategory1": "refinedresources",
            },
            {
                "@uniquename": "T4_WOOD",
                "@tier": "4",
                "@weight": "0.4",
                "@shopcategory": "crafting",
                "@shopsubcategory1": "resources",
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
        # Grupo que vem como objeto único e não como lista.
        "hideoutitem": {"@uniquename": "UNIQUE_HIDEOUT", "@weight": "100"},
    }
}


def names_entry(unique_name: str, en: str | None = None, pt: str | None = None) -> dict:
    localized = {}
    if en:
        localized["EN-US"] = en
    if pt:
        localized["PT-BR"] = pt
    return {"UniqueName": unique_name, "LocalizedNames": localized}


def test_index_metadata_achata_listas_e_objetos():
    index = index_metadata(METADATA)
    assert set(index) == {"T4_PLANKS", "T4_WOOD", "T4_BAG", "UNIQUE_HIDEOUT"}


class TestNormalize:
    index = index_metadata(METADATA)

    def test_item_base_pega_metadado_do_dump(self):
        item = normalize(names_entry("T4_PLANKS", "Pine Planks", "Tábuas de Pinho"), self.index)
        assert item is not None
        assert item.tier == 4
        assert item.enchantment == 0
        assert item.weight == 0.51
        assert item.category_code == "crafting"
        assert item.subcategory_code == "refinedresources"
        assert item.display_name_pt == "Tábuas de Pinho"
        assert item.is_tracked is True
        assert item.has_metadata is True

    def test_variante_encantada_herda_metadado_da_base(self):
        """T4_PLANKS_LEVEL1@1 não existe no dump; T4_PLANKS existe."""
        item = normalize(names_entry("T4_PLANKS_LEVEL1@1", pt="Tábuas Incomuns"), self.index)
        assert item is not None
        assert item.base_name == "T4_PLANKS"
        assert item.enchantment == 1
        assert item.tier == 4
        assert item.weight == 0.51

    def test_equipamento_encantado(self):
        item = normalize(names_entry("T4_BAG@2", "Adept's Bag"), self.index)
        assert item is not None
        assert item.base_name == "T4_BAG"
        assert item.enchantment == 2
        assert item.max_quality == 5
        assert item.is_tracked is False

    def test_sem_metadado_gera_null_em_vez_de_chute(self):
        """Requisito 52: campo desconhecido é NULL, nunca um valor plausível."""
        item = normalize(names_entry("T3_JOURNAL_WOOD_EMPTY"), self.index)
        assert item is not None
        assert item.has_metadata is False
        assert item.weight is None
        assert item.category_code is None
        assert item.max_quality is None
        # Tier ainda sai do identificador, que é informação de verdade.
        assert item.tier == 3

    def test_tier_ausente_no_identificador_e_no_dump_fica_null(self):
        item = normalize(names_entry("UNIQUE_HIDEOUT"), self.index)
        assert item is not None
        assert item.tier is None

    def test_nome_localizado_ausente_fica_null(self):
        item = normalize(names_entry("T4_WOOD"), self.index)
        assert item is not None
        assert item.display_name_en is None
        assert item.display_name_pt is None

    def test_entrada_sem_identificador_e_descartada(self):
        assert normalize({"UniqueName": "   "}, self.index) is None

    def test_lista_de_rastreio_e_parametrizavel(self):
        item = normalize(names_entry("T4_WOOD"), self.index, frozenset({"resources"}))
        assert item is not None
        assert item.is_tracked is True
