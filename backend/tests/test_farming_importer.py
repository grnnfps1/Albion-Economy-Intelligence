"""Leitura de `farmableitem` e das listas de loot.

Payloads fiéis ao dump, encurtados. As armadilhas que estes testes cercam são as
mesmas de sempre neste projeto: o dump é irregular, e o que ele diz precisa ser
lido, não suposto.
"""

from app.catalog.farming_importer import loot_entries, normalize, parse_amount

CENOURA = {
    "@uniquename": "T1_FARM_CARROT_SEED",
    "@tier": "1",
    "@shopcategory": "farming",
    "@shopsubcategory1": "farm",
    "@shopsubcategory2": "seeds",
    "@activefarmfocuscost": "1000",
    "@activefarmmaxcycles": "1",
    "@activefarmactiondurationseconds": "1",
    "@activefarmcyclelengthseconds": "79200",
    "@activefarmbonus": "2.0",
    "craftingrequirements": {"@silver": "2000", "@time": "0", "@swaptransaction": "true"},
    "harvest": {
        "@growtime": "79200",
        "@lootlist": "T1_CARROT_LOOT",
        "@lootchance": "1",
        "@fame": "100",
        "seed": {"@chance": "0.3333", "@amount": "1"},
    },
}

BOI = {
    "@uniquename": "T3_FARM_OX_BABY",
    "@tier": "3",
    "@shopcategory": "farming",
    "@shopsubcategory1": "pasture",
    "@shopsubcategory2": "babys",
    "@activefarmfocuscost": "1000",
    "@activefarmmaxcycles": "1",
    "@activefarmcyclelengthseconds": "79200",
    "craftingrequirements": {"@silver": "25000"},
    "grownitem": {
        "@uniquename": "T3_FARM_OX_GROWN",
        "@growtime": "158400",
        "@fame": "100",
        "offspring": {"@chance": "0.8400", "@amount": "1"},
    },
    "consumption": {
        "food": {
            "@nutritionmax": "480",
            "@secondspernutrition": "330",
            "acceptedfood": {"@foodcategory": "plants"},
        }
    },
}

VACA = {
    "@uniquename": "T8_FARM_COW_GROWN",
    "@tier": "8",
    "@shopcategory": "farming",
    "@shopsubcategory1": "pasture",
    "@shopsubcategory2": "animals",
    "products": {
        "product": {
            "@productiontime": "79200",
            "@lootlist": "T8_COW_LOOT",
            "@lootchance": "1",
        }
    },
    "consumption": {
        "food": {
            "@nutritionmax": "9000",
            "@secondspernutrition": "91.67",
            "acceptedfood": {"@foodcategory": "plants", "@favorite": "T8_PUMPKIN",
                             "@favoritebonus": "1"},
        }
    },
}

LOOT = {
    "T1_CARROT_LOOT": {
        "@name": "T1_CARROT_LOOT",
        "Item": [
            {"@type": "T1_CARROT", "@chance": "1.0", "@amount": "3-6"},
            {"@type": "T1_WORM", "@chance": "0.1", "@amount": "1"},
        ],
    },
    "T8_COW_LOOT": {
        "@name": "T8_COW_LOOT",
        # Objeto, não lista: o dump usa as duas formas para o mesmo campo.
        "Item": {"@type": "T8_MILK", "@chance": "1", "@amount": "7-11"},
    },
}


def test_faixa_de_quantidade_vira_par():
    """`3-6` não é 4 nem 6: é uma faixa, e ela precisa sobreviver à leitura."""
    assert parse_amount("3-6") == (3, 6)
    assert parse_amount("1") == (1, 1)
    assert parse_amount(None) == (1, 1)
    assert parse_amount("lixo") == (1, 1)


def test_item_da_lista_de_loot_pode_ser_objeto_ou_lista():
    """Mesma armadilha de `craftingrequirements` em receitas."""
    assert len(loot_entries(LOOT["T1_CARROT_LOOT"])) == 2
    assert loot_entries(LOOT["T8_COW_LOOT"]) == [("T8_MILK", 7, 11, 1.0)]
    assert loot_entries(None) == []


def test_cultivo_resolve_a_lista_de_loot():
    """`@lootlist` é só o nome: sem resolver, não se sabe o que a colheita dá."""
    normalizado = normalize(CENOURA, LOOT)

    assert normalizado.station == "farm"
    assert normalizado.role == "seed"
    assert normalizado.grow_seconds == 79_200
    assert normalizado.cycle_seconds == 79_200
    assert normalizado.focus_cost == 1000
    assert normalizado.npc_silver_cost == 2000

    colheita = {s.unique_name: s for s in normalizado.outputs}
    assert colheita["T1_CARROT"].amount_min == 3
    assert colheita["T1_CARROT"].amount_max == 6
    assert colheita["T1_CARROT"].role == "harvest"
    # A minhoca cai junto e não é o motivo de plantar cenoura.
    assert colheita["T1_WORM"].chance == 0.1


def test_semente_que_volta_aponta_para_a_propria_semente():
    normalizado = normalize(CENOURA, LOOT)
    volta = next(s for s in normalizado.outputs if s.role == "seed_return")
    assert volta.unique_name == "T1_FARM_CARROT_SEED"
    assert volta.chance == 0.3333


def test_criacao_traz_o_adulto_a_cria_e_a_racao():
    normalizado = normalize(BOI, LOOT)

    assert normalizado.role == "baby"
    assert normalizado.grown_unique_name == "T3_FARM_OX_GROWN"
    # O tempo que conta na criação é o de crescer, não o do ciclo de Focus.
    assert normalizado.grow_seconds == 158_400
    assert normalizado.accepted_food_category == "plants"
    assert normalizado.seconds_per_nutrition == 330.0

    papeis = {s.role: s for s in normalizado.outputs}
    assert papeis["grown"].unique_name == "T3_FARM_OX_GROWN"
    assert papeis["offspring"].unique_name == "T3_FARM_OX_BABY"
    assert papeis["offspring"].chance == 0.84


def test_adulto_que_produz_leite_tem_intervalo_proprio():
    normalizado = normalize(VACA, LOOT)

    assert normalizado.role == "grown"
    assert normalizado.product_seconds == 79_200
    assert normalizado.grow_seconds is None
    assert normalizado.favorite_food == "T8_PUMPKIN"
    produto = next(s for s in normalizado.outputs if s.role == "product")
    assert (produto.unique_name, produto.amount_min, produto.amount_max) == ("T8_MILK", 7, 11)


def test_entrada_fora_das_quatro_estacoes_e_ignorada():
    """Nem tudo em `farmableitem` é fazenda: o que não encaixa não vira linha."""
    assert normalize({"@uniquename": "X", "@shopsubcategory1": "outro"}, LOOT) is None
    assert normalize({"@shopsubcategory1": "farm", "@shopsubcategory2": "seeds"}, LOOT) is None
