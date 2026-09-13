"""URL do ícone: função pura, derivada do identificador."""

import pytest

from app.catalog.icons import item_icon_url


def test_item_base():
    url = item_icon_url("T5_LEATHER", quality=2, size=64)
    assert url == "https://render.albiononline.com/v1/item/T5_LEATHER.png?quality=2&size=64"


def test_encantamento_vai_no_proprio_identificador():
    """O serviço de render entende o sufixo @N. Nada precisa ser recomposto."""
    assert "T4_BAG@1.png" in item_icon_url("T4_BAG@1")


def test_recurso_refinado_encantado():
    assert "T4_PLANKS_LEVEL1@1.png" in item_icon_url("T4_PLANKS_LEVEL1@1")


@pytest.mark.parametrize(("entrada", "esperado"), [(0, 1), (1, 1), (5, 5), (9, 5)])
def test_qualidade_e_limitada_a_faixa_do_servico(entrada, esperado):
    assert f"quality={esperado}" in item_icon_url("T4_BAG", quality=entrada)


@pytest.mark.parametrize(("entrada", "esperado"), [(0, 1), (64, 64), (500, 217)])
def test_tamanho_e_limitado_a_faixa_do_servico(entrada, esperado):
    assert f"size={esperado}" in item_icon_url("T4_BAG", size=entrada)


@pytest.mark.parametrize("identificador", ["", "   "])
def test_identificador_vazio_nao_gera_url_quebrada(identificador):
    """None é tratável pela UI; uma imagem que dá 404 em toda linha, não."""
    assert item_icon_url(identificador) is None
