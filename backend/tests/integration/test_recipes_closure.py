"""`recipes_for_chain`: pedir as receitas que a cadeia alcança, e só elas.

`/refining` e o calculador pediam as **12.917 receitas do jogo** para usar
algumas centenas. O filtro estava no lugar errado: o chamador descartava 97% do
que pedia, depois de o ORM já ter construído os objetos.

Estes testes travam as duas propriedades que fazem a troca ser segura: o fecho
é **exato** (nenhuma receita alcançável fica de fora) e **completo por saída**
(quem entra, entra com todas as suas variantes).
"""

import pytest

from app.models.catalog import Item
from app.models.recipes import Recipe, RecipeMaterial
from app.repositories import recipes_repo

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def cadeia(session):
    """Uma cadeia com a armadilha real: recurso **bruto** que tem receita.

    `T4_WOOD_LEVEL1@1` se faz de `T4_WOOD` mais material de encantamento, e não
    é `refinedresources`. Filtrar por subcategoria deixaria essa receita de
    fora, a cadeia pararia de descer e trataria o bruto encantado como fim de
    linha — com o preço de mercado dele. O custo sairia diferente, e nada
    acusaria.
    """
    itens = {}
    for nome, sub in [
        ("T4_PLANKS", "refinedresources"),
        ("T3_PLANKS", "refinedresources"),
        ("T4_WOOD", "resources"),
        ("T3_WOOD", "resources"),
        ("T4_WOOD_LEVEL1@1", "resources"),
        ("T4_RUNE", "resources"),
        # Fora da cadeia: existe, tem receita, e não pode ser carregado.
        ("T4_HEAD_PLATE_SET1", "armor"),
        ("T4_METALBAR", "refinedresources"),
    ]:
        itens[nome] = Item(
            unique_name=nome, base_name=nome, tier=4, enchantment=0,
            subcategory_code=sub, is_tracked=True,
        )
    session.add_all(itens.values())
    await session.flush()

    def receita(saida, materiais, variante=0):
        r = Recipe(
            output_item_id=itens[saida].id, variant_index=variante, output_quantity=1,
            focus_cost=10, silver_cost=0, station_category="wood",
        )
        session.add(r)
        return r, materiais

    pendentes = [
        receita("T4_PLANKS", [("T4_WOOD", 2), ("T3_PLANKS", 1)]),
        # Segunda variante da MESMA saída: quem entra, entra inteiro.
        receita("T4_PLANKS", [("T4_WOOD", 1), ("T4_RUNE", 1)], variante=1),
        receita("T3_PLANKS", [("T3_WOOD", 2)]),
        # A armadilha: bruto encantado com receita própria.
        receita("T4_WOOD_LEVEL1@1", [("T4_WOOD", 1), ("T4_RUNE", 1)]),
        # Fora da cadeia do T4_PLANKS.
        receita("T4_HEAD_PLATE_SET1", [("T4_METALBAR", 2)]),
    ]
    await session.flush()
    for r, materiais in pendentes:
        for nome, qtd in materiais:
            session.add(
                RecipeMaterial(
                    recipe_id=r.id, item_id=itens[nome].id, quantity=qtd,
                    is_returnable=True,
                )
            )
    await session.flush()
    return itens


async def nomes_de_saida(session, receitas, itens):
    por_id = {i.id: nome for nome, i in itens.items()}
    return sorted(por_id[r.output_item_id] for r in receitas)


async def test_traz_a_cadeia_inteira_a_partir_da_semente(session, cadeia):
    receitas = await recipes_repo.recipes_for_chain(session, [cadeia["T4_PLANKS"].id])
    assert await nomes_de_saida(session, receitas, cadeia) == [
        "T3_PLANKS", "T4_PLANKS", "T4_PLANKS",
    ]


async def test_nao_traz_o_que_esta_fora_da_cadeia(session, cadeia):
    """A receita de armadura existe, tem material, e não pode ser carregada."""
    receitas = await recipes_repo.recipes_for_chain(session, [cadeia["T4_PLANKS"].id])
    assert "T4_HEAD_PLATE_SET1" not in await nomes_de_saida(session, receitas, cadeia)


async def test_quem_entra_entra_com_TODAS_as_variantes(session, cadeia):
    """Variante é escolha do motor: ele compara custos e fica com a mais barata.

    Trazer só uma faria o motor escolher entre uma opção, em silêncio — que é
    exatamente o bug que a fase 19 corrigiu.
    """
    receitas = await recipes_repo.recipes_for_chain(session, [cadeia["T4_PLANKS"].id])
    variantes = [r.variant_index for r in receitas
                 if r.output_item_id == cadeia["T4_PLANKS"].id]
    assert sorted(variantes) == [0, 1]


async def test_recurso_bruto_ENCANTADO_tem_receita_e_entra(session, cadeia):
    """A armadilha que derruba o filtro por subcategoria.

    `T4_WOOD_LEVEL1@1` é `resources`, não `refinedresources`, e mesmo assim tem
    receita. Filtrar por subcategoria o deixaria de fora e a cadeia pararia de
    descer — sem erro, com outro custo.
    """
    receitas = await recipes_repo.recipes_for_chain(
        session, [cadeia["T4_WOOD_LEVEL1@1"].id]
    )
    assert await nomes_de_saida(session, receitas, cadeia) == ["T4_WOOD_LEVEL1@1"]


async def test_semente_sem_receita_devolve_vazio(session, cadeia):
    """Recurso bruto puro é fim natural da cadeia, não erro."""
    assert await recipes_repo.recipes_for_chain(session, [cadeia["T3_WOOD"].id]) == []


async def test_semente_vazia_nao_consulta_nada(session, cadeia):
    assert await recipes_repo.recipes_for_chain(session, []) == []


async def test_e_equivalente_a_carregar_tudo_e_descartar(session, cadeia):
    """A propriedade que autoriza a troca: mesmo resultado, menos trabalho.

    Para toda saída que o fecho traz, o conjunto de variantes é **idêntico** ao
    que a carga completa daria. E nenhum item alcançado com receita fica de
    fora.
    """
    todas = await recipes_repo.list_recipes(session, tracked_only=False, limit=50_000)
    fecho = await recipes_repo.recipes_for_chain(session, [cadeia["T4_PLANKS"].id])

    completo: dict[int, set[int]] = {}
    for r in todas:
        completo.setdefault(r.output_item_id, set()).add(r.id)
    reduzido: dict[int, set[int]] = {}
    for r in fecho:
        reduzido.setdefault(r.output_item_id, set()).add(r.id)

    for saida, ids in reduzido.items():
        assert ids == completo[saida]

    alcancados = {cadeia["T4_PLANKS"].id}
    for r in fecho:
        alcancados.update(m.item_id for m in r.materials)
    assert not (alcancados & set(completo)) - set(reduzido)
