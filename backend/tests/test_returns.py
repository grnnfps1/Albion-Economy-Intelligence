"""A matriz de retorno e a cidade que rende mais.

O que estes testes protegem: que a cidade deixe de ser invisível na conta. Com
um valor único de retorno, a diferença entre refinar em Thetford e refinar em
Caerleon não aparecia em lugar nenhum.
"""

import pytest

from app.calculations.returns import (
    Activity,
    ReturnMatrix,
    resolve_return_rate,
)
from app.services.return_service import ReturnPolicy, base_token, family_of

REFINO = ReturnMatrix(bonus_base=0.367, bonus_focus=0.539, base=0.152, focus=0.435)
CRAFT = ReturnMatrix(bonus_base=0.248, bonus_focus=0.477, base=0.152, focus=0.435)

POLITICA = ReturnPolicy(
    matrices={Activity.REFINING: REFINO, Activity.CRAFTING: CRAFT},
    craft_families={
        "bridgewatch": ["ARMOR_PLATE", "2H_CROSSBOW"],
        "lymhurst": ["2H_BOW", "MAIN_SWORD"],
    },
    refine_resources={
        "thetford": ["ORE", "METALBAR"],
        "fort-sterling": ["WOOD", "PLANKS"],
        "caerleon": [],
    },
)


def test_a_celula_certa_por_cidade_e_focus():
    assert REFINO.cell(has_city_bonus=True, use_focus=False) == 0.367
    assert REFINO.cell(has_city_bonus=True, use_focus=True) == 0.539
    assert REFINO.cell(has_city_bonus=False, use_focus=False) == 0.152
    assert REFINO.cell(has_city_bonus=False, use_focus=True) == 0.435


def test_mudar_de_cidade_rende_mais_que_ficar_sem_focus():
    """A decisão que o valor único escondia.

    Refinar na cidade certa sem Focus (0,367) rende mais que o dobro de refinar
    na cidade errada sem Focus (0,152).
    """
    certa = resolve_return_rate(REFINO, has_city_bonus=True, use_focus=False).rate
    errada = resolve_return_rate(REFINO, has_city_bonus=False, use_focus=False).rate
    assert certa > errada * 2


def test_bonus_diario_soma_a_celula():
    resolvido = resolve_return_rate(REFINO, True, True, daily_bonus=0.20)
    assert resolvido.rate == pytest.approx(0.739)
    assert resolvido.matrix_rate == 0.539
    assert resolvido.daily_bonus == 0.20


def test_taxa_nunca_passa_de_um():
    """Célula alta mais bônus diário não pode virar retorno acima de 100%."""
    assert resolve_return_rate(REFINO, True, True, daily_bonus=0.9).rate == 1.0


def test_preferencia_do_usuario_sobrescreve_a_matriz():
    """Sobrescrita opcional, não valor primário."""
    resolvido = resolve_return_rate(REFINO, True, True, override=0.20)
    assert resolvido.rate == pytest.approx(0.20)
    assert resolvido.source == "preferencia"
    # A célula continua na resposta, para dar para comparar.
    assert resolvido.matrix_rate == 0.539


def test_celula_desconhecida_vira_unknown_e_nao_zero():
    vazia = ReturnMatrix()
    resolvido = resolve_return_rate(vazia, True, True)
    assert resolvido.rate is None
    assert resolvido.known is False
    assert resolvido.source == "UNKNOWN"


def test_familia_de_recurso_sai_do_nome():
    assert family_of("T5_PLANKS") == "PLANKS"
    assert family_of("T5_PLANKS_LEVEL2@2") == "PLANKS"
    assert family_of("UNIQUE_HIDEOUT") is None


def test_token_base_ignora_tier_e_encantamento():
    assert base_token("T4_2H_BOW@1") == "2H_BOW"
    assert base_token("T8_ARMOR_PLATE_SET3") == "ARMOR_PLATE_SET3"


def test_bonus_de_refino_segue_o_recurso():
    assert POLITICA.bonus_city(Activity.REFINING, "T5_METALBAR") == "thetford"
    assert POLITICA.bonus_city(Activity.REFINING, "T4_PLANKS@2") == "fort-sterling"
    # Couro não está no mapa desta fixture: sem bônus, não um bônus inventado.
    assert POLITICA.bonus_city(Activity.REFINING, "T5_LEATHER") is None


def test_caerleon_sem_bonus_e_afirmacao_e_nao_lacuna():
    """Lista vazia no mapa é diferente de a cidade não estar no mapa."""
    assert POLITICA.bonus_city(Activity.REFINING, "T5_METALBAR") != "caerleon"


def test_bonus_de_craft_casa_por_prefixo_e_nao_por_substring():
    """`2H_BOW` não pode pegar `2H_CROSSBOW`, que é de outra cidade."""
    assert POLITICA.bonus_city(Activity.CRAFTING, "T6_2H_BOW") == "lymhurst"
    assert POLITICA.bonus_city(Activity.CRAFTING, "T6_2H_CROSSBOW") == "bridgewatch"
    assert POLITICA.bonus_city(Activity.CRAFTING, "T6_2H_BOW_AVALON") == "lymhurst"


def test_item_sem_familia_mapeada_fica_sem_bonus():
    """Errar para menos retorno é o lado conservador."""
    assert POLITICA.bonus_city(Activity.CRAFTING, "T6_2H_QUARTERSTAFF") is None


def test_resolve_devolve_a_cidade_que_renderia_mais():
    atual, melhor = POLITICA.resolve(
        Activity.REFINING, "T5_METALBAR", city_slug="caerleon", use_focus=False
    )
    assert atual.rate == 0.152
    assert melhor.city_slug == "thetford"
    assert melhor.rate_there == 0.367
    assert melhor.delta == pytest.approx(0.215, abs=0.0001)
    assert melhor.is_here is False


def test_quando_ja_se_esta_na_cidade_certa_nao_ha_o_que_recomendar():
    atual, melhor = POLITICA.resolve(
        Activity.REFINING, "T5_METALBAR", city_slug="thetford", use_focus=False
    )
    assert atual.rate == 0.367
    assert melhor.city_slug == "thetford"
    assert melhor.is_here is True
    assert melhor.delta == 0


def test_sem_mapeamento_de_refino_nao_ha_recomendacao():
    """UNKNOWN precisa chegar à tela como 'não levantado', não como 'sem bônus'."""
    sem_mapa = ReturnPolicy(matrices={Activity.REFINING: REFINO}, refine_resources=None)
    _atual, melhor = sem_mapa.resolve(
        Activity.REFINING, "T5_METALBAR", city_slug="caerleon", use_focus=False
    )
    assert melhor.city_slug is None
    assert melhor.known is False
