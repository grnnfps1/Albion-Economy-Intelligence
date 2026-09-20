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
                "@itemvalue": "16",
                "@shopcategory": "crafting",
                "@shopsubcategory1": "refinedresources",
            },
            # A variante encantada existe no dump com peso idêntico e
            # `@itemvalue` **dobrado**. É a diferença que a fase 15 explora.
            {
                "@uniquename": "T4_PLANKS_LEVEL1",
                "@tier": "4",
                "@weight": "0.51",
                "@itemvalue": "32",
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
    assert set(index) == {
        "T4_PLANKS", "T4_PLANKS_LEVEL1", "T4_WOOD", "T4_BAG", "UNIQUE_HIDEOUT",
    }


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
        assert item.item_value == 16
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

    def test_item_value_do_encantado_nao_herda_o_da_base(self):
        """A exceção ao agrupamento por `base_name` -- e ela infla lucro.

        Peso, tier e categoria são iguais entre `T4_PLANKS` e
        `T4_PLANKS_LEVEL1`, então herdar a raiz sempre funcionou. `@itemvalue`
        não: 16 contra 32, e no encantamento 4 é 16×. Como a taxa da estação sai
        dele, herdar a base cobraria taxa de item comum num item encantado.
        """
        base = normalize(names_entry("T4_PLANKS"), self.index)
        encantado = normalize(names_entry("T4_PLANKS_LEVEL1@1"), self.index)
        assert base.item_value == 16
        assert encantado.item_value == 32
        # O agrupamento continua o mesmo: só o valor do item se separa.
        assert encantado.base_name == "T4_PLANKS"

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
        assert item.item_value is None
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
        item = normalize(
            names_entry("T4_WOOD", "Rough Logs", "Troncos Rústicos"),
            self.index,
            frozenset({"resources"}),
        )
        assert item is not None
        assert item.is_tracked is True

    def test_item_sem_nome_em_nenhum_idioma_nao_e_rastreado(self):
        """Item sem `display_name` nos dois idiomas não é item de mercado.

        Medido em 20/09/2026: os 30 itens rastreados sem nome nenhum — os
        `CRYSTALLEAGUE_*_TEMPLATE` e o cristal de arena — **nunca** tiveram
        cotação, e o AODP devolve as 35 linhas deles zeradas. Eram 6,6% de cada
        varredura completa gastos em item que ninguém compra.

        O critério é a ausência de nome, e não "nunca teve cotação": montaria
        rara e rédea decorativa também não têm ordem observada, e **continuam
        rastreadas** porque têm nome e são itens de verdade. Ausência de mercado
        observado não é ausência de mercado.
        """
        item = normalize(names_entry("T4_WOOD"), self.index, frozenset({"resources"}))
        assert item is not None
        assert item.is_tracked is False

    def test_nome_em_um_idioma_so_ja_basta(self):
        """O corte é "não tem nome em lugar nenhum", não "falta o português"."""
        so_en = normalize(
            names_entry("T4_WOOD", en="Rough Logs"), self.index, frozenset({"resources"})
        )
        so_pt = normalize(
            names_entry("T4_WOOD", pt="Troncos Rústicos"), self.index, frozenset({"resources"})
        )
        assert so_en is not None and so_en.is_tracked is True
        assert so_pt is not None and so_pt.is_tracked is True
