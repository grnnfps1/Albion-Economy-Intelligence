"""Lotes limitados pelo comprimento da URL, não por contagem de itens."""

import pytest

from app.collectors.aodp.batching import ItemNameTooLong, batch_item_names, build_url

BASE = "https://west.albion-online-data.com"
PATH = "/api/v2/stats/prices/{item_ids}.json"
PARAMS = {"locations": "Caerleon,Bridgewatch", "qualities": "1,2"}


def test_url_montada_como_vai_para_a_rede():
    url = build_url(BASE, PATH, ["T4_BAG", "T5_BAG"], {"locations": "Caerleon"})
    assert url == (
        "https://west.albion-online-data.com/api/v2/stats/prices/"
        "T4_BAG,T5_BAG.json?locations=Caerleon"
    )


def test_nome_com_espaco_e_codificado_e_conta_mais():
    """`Fort Sterling` vira `Fort%20Sterling`: medir a string crua subestima."""
    url = build_url(BASE, PATH, ["T4_BAG"], {"locations": "Fort Sterling"})
    assert "Fort+Sterling" in url or "Fort%20Sterling" in url


def test_lote_unico_quando_tudo_cabe():
    batches = list(batch_item_names(["T4_BAG", "T5_BAG"], BASE, PATH, PARAMS, 4096))
    assert batches == [["T4_BAG", "T5_BAG"]]


def test_divide_quando_estoura_o_limite():
    names = [f"T{tier}_PLANKS_LEVEL{tier}@{tier % 5}" for tier in range(2, 9)]
    limit = len(build_url(BASE, PATH, names[:2], PARAMS)) + 2

    batches = list(batch_item_names(names, BASE, PATH, PARAMS, limit))

    assert len(batches) > 1
    for batch in batches:
        assert len(build_url(BASE, PATH, batch, PARAMS)) <= limit
    # Nenhum item se perde nem é duplicado.
    assert [name for batch in batches for name in batch] == names


def test_nenhum_lote_passa_de_4096_com_catalogo_grande():
    """Limite real do AODP, com nomes longos de verdade."""
    names = [f"T8_2H_HOLYSTAFF_MORGANA_VARIANT_{index}@3" for index in range(400)]

    batches = list(batch_item_names(names, BASE, PATH, PARAMS, 4096))

    assert sum(len(batch) for batch in batches) == 400
    assert all(len(build_url(BASE, PATH, batch, PARAMS)) <= 4096 for batch in batches)


def test_item_que_nao_cabe_sozinho_falha_alto():
    """Silenciar isso faria o item sumir da coleta sem ninguém notar."""
    with pytest.raises(ItemNameTooLong):
        list(batch_item_names(["T4_BAG"], BASE, PATH, PARAMS, 50))


def test_lista_vazia_nao_gera_lote():
    assert list(batch_item_names([], BASE, PATH, PARAMS, 4096)) == []


def test_ordem_preservada():
    names = ["T2_BAG", "T3_BAG", "T4_BAG", "T5_BAG"]
    limit = len(build_url(BASE, PATH, names[:1], PARAMS)) + 1
    batches = list(batch_item_names(names, BASE, PATH, PARAMS, limit))
    assert [name for batch in batches for name in batch] == names
