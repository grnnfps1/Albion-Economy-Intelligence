"""Parsing das receitas do dump.

O dump é irregular de três formas independentes, e cada uma já custou um bug:
`craftingrequirements` pode ser objeto ou lista; o material encantado vem sem o
sufixo de mercado; e a **saída** encantada também, quando o item é entrada de
primeiro nível.

Este arquivo nasceu na fase 19, junto com a correção do terceiro caso — não
havia teste nenhum do importador de receitas até então, que é como 80 recursos
ficaram sem receita sem ninguém notar.
"""

from app.catalog.recipes_importer import material_candidates, parse_entry


class TestMaterialEncantado:
    def test_material_encantado_ganha_o_sufixo_de_mercado(self):
        """O dump diz `T4_ROCK_LEVEL1`; o catálogo e o AODP dizem `@1`."""
        assert material_candidates("T4_ROCK_LEVEL1", 1) == (
            "T4_ROCK_LEVEL1@1",
            "T4_ROCK_LEVEL1",
        )

    def test_material_sem_encantamento_fica_como_esta(self):
        assert material_candidates("T4_ROCK", 0) == ("T4_ROCK",)


class TestFormaIrregular:
    def test_craftingrequirements_como_objeto_unico(self):
        entrada = {
            "@uniquename": "T4_PLANKS",
            "craftingrequirements": {
                "@craftingfocus": "54",
                "craftresource": {"@uniquename": "T4_WOOD", "@count": "2"},
            },
        }
        receitas = parse_entry(entrada)
        assert len(receitas) == 1
        assert receitas[0].focus_cost == 54

    def test_receitas_alternativas_viram_variantes(self):
        """`T4_PLANKS` sai de 2x madeira **ou** de 1x madeira + token."""
        entrada = {
            "@uniquename": "T4_PLANKS",
            "craftingrequirements": [
                {"craftresource": {"@uniquename": "T4_WOOD", "@count": "2"}},
                {
                    "craftresource": [
                        {"@uniquename": "T4_WOOD", "@count": "1"},
                        {"@uniquename": "T1_FACTION_FOREST_TOKEN_1", "@count": "1"},
                    ]
                },
            ],
        }
        receitas = parse_entry(entrada)
        assert [r.variant_index for r in receitas] == [0, 1]




class TestSaidaEncantadaDePrimeiroNivel:
    """Recurso refinado encantado é entrada própria no dump, não aninhada.

    `T6_LEATHER_LEVEL1` tem `@enchantmentlevel: 1` e `craftingrequirements`
    próprios — diferente de equipamento, que aninha em `enchantments`. A saída
    precisa virar `@1` como o catálogo a chama, senão a receita é descartada em
    silêncio. Foram 80 recursos sem receita até a fase 19.
    """

    ENTRADA = {
        "@uniquename": "T6_LEATHER_LEVEL1",
        "@enchantmentlevel": "1",
        "@craftingcategory": "leather",
        "craftingrequirements": [
            {
                "@craftingfocus": "164",
                "@amountcrafted": "1",
                "craftresource": [
                    {"@uniquename": "T6_HIDE_LEVEL1", "@count": "4", "@enchantmentlevel": "1"},
                    {"@uniquename": "T5_LEATHER_LEVEL1", "@count": "1", "@enchantmentlevel": "1"},
                ],
            }
        ],
    }

    def test_a_saida_ganha_o_sufixo_de_mercado(self):
        receitas = parse_entry(self.ENTRADA)
        assert [r.output_unique_name for r in receitas] == ["T6_LEATHER_LEVEL1@1"]

    def test_a_cadeia_encantada_e_paralela_a_normal(self):
        """T6 encantado consome T5 **encantado**, não o T5 comum."""
        materiais = parse_entry(self.ENTRADA)[0].materials
        candidatos = [c[0] for c in materiais]
        assert ("T5_LEATHER_LEVEL1@1", "T5_LEATHER_LEVEL1") in candidatos
        assert ("T6_HIDE_LEVEL1@1", "T6_HIDE_LEVEL1") in candidatos

    def test_item_sem_encantamento_nao_ganha_sufixo(self):
        base = {
            "@uniquename": "T6_LEATHER",
            "@enchantmentlevel": "0",
            "craftingrequirements": [{"craftresource": {"@uniquename": "T6_HIDE", "@count": "4"}}],
        }
        assert parse_entry(base)[0].output_unique_name == "T6_LEATHER"
