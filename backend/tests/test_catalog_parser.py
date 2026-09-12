"""Parser de identificador de item.

Funções puras, então dá para cobrir os formatos reais sem banco e sem rede.
Os exemplos vêm de `formatted/items.txt` do dump oficial.
"""

import pytest

from app.catalog.parser import InvalidItemName, parse_item_name, resolve_base_name


@pytest.mark.parametrize(
    ("unique_name", "tier", "enchantment"),
    [
        ("T4_PLANKS", 4, 0),
        ("T4_BAG@1", 4, 1),
        ("T8_2H_HOLYSTAFF_MORGANA@3", 8, 3),
        ("T5_LEATHER_LEVEL4@4", 5, 4),
        ("T1_FACTION_FOREST_TOKEN_1", 1, 0),
        ("UNIQUE_HIDEOUT", None, 0),
        ("TREASURE_KNOWLEDGE_RARITY1", None, 0),
    ],
)
def test_tier_e_encantamento(unique_name, tier, enchantment):
    parsed = parse_item_name(unique_name)
    assert parsed.tier == tier
    assert parsed.enchantment == enchantment
    assert parsed.unique_name == unique_name


def test_item_sem_tier_nao_recebe_tier_chutado():
    """Requisito 52: sem informação, NULL -- não '1' por padrão."""
    assert parse_item_name("UNIQUE_HIDEOUT").tier is None


def test_sufixo_arroba_manda_no_encantamento():
    assert parse_item_name("T4_PLANKS_LEVEL1@1").enchantment == 1


@pytest.mark.parametrize(
    "unique_name", ["", "   ", "T4_BAG@x", "T4_BAG@9", "@1"]
)
def test_identificadores_invalidos_falham_alto(unique_name):
    with pytest.raises(InvalidItemName):
        parse_item_name(unique_name)


class TestResolveBaseName:
    """`_LEVELN` é ambíguo: às vezes é encantamento, às vezes faz parte do nome."""

    def test_level_e_variante_encantada_quando_a_raiz_existe(self):
        parsed = parse_item_name("T4_PLANKS_LEVEL1@1")
        dump = {"T4_PLANKS"}
        assert resolve_base_name(parsed, dump.__contains__) == "T4_PLANKS"

    def test_level_faz_parte_do_nome_quando_a_raiz_nao_existe(self):
        """T1_FISHSAUCE_LEVEL1/2/3 são itens distintos, não encantamentos."""
        parsed = parse_item_name("T1_FISHSAUCE_LEVEL1")
        dump = {"T1_FISHSAUCE_LEVEL1", "T1_FISHSAUCE_LEVEL2"}
        assert resolve_base_name(parsed, dump.__contains__) == "T1_FISHSAUCE_LEVEL1"

    def test_sem_nenhum_candidato_no_dump_cai_no_literal(self):
        parsed = parse_item_name("T9_INVENTADO@2")
        assert resolve_base_name(parsed, lambda _key: False) == "T9_INVENTADO"

    def test_encantamento_de_equipamento_agrupa_pela_base(self):
        parsed = parse_item_name("T4_BAG@3")
        assert resolve_base_name(parsed, {"T4_BAG"}.__contains__) == "T4_BAG"
