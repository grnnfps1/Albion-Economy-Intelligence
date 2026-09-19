"""Calculador de crafting: a tabela de uma família, com preço editável."""

from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.aodp.normalization import MarketPriceRecord
from app.models.catalog import Item
from app.models.manual_price import KIND_SELL
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, Location, Server
from app.repositories import manual_prices as manual_repo
from app.repositories import market as market_repo
from app.services.calculator_service import build_calculator

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)
USUARIO = "discord-7"

PADRAO = dict(
    server="west", family="LEATHER", buy_location="caerleon", sell_location="caerleon",
    quantity=100, station_fee_per_100_nutrition=184,
    setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True,
    return_rate=0.0, use_focus=False, daily_production_bonus=0.0,
    spec_levels=None, spec_item_levels=None, focus_per_day=None, user_id=None,
)

PRECOS = {
    "T2_HIDE": 50, "T3_HIDE": 100, "T4_HIDE": 200,
    "T2_LEATHER": 80, "T3_LEATHER": 300, "T4_LEATHER": 1000,
    "T1_FACTION_STEPPE_TOKEN_1": 10,
}


@pytest.fixture
async def familia(session):
    """Couro T2 a T4, com a variante de token no T4."""
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    session.add_all([server, caerleon, source])
    await session.flush()

    itens: dict[str, Item] = {}
    for tier in (2, 3, 4):
        itens[f"T{tier}_HIDE"] = Item(
            unique_name=f"T{tier}_HIDE", base_name=f"T{tier}_HIDE", tier=tier, enchantment=0,
            display_name_pt=f"Pelego T{tier}", subcategory_code="resources",
            item_value=2 ** (tier - 1), is_tracked=True,
        )
        itens[f"T{tier}_LEATHER"] = Item(
            unique_name=f"T{tier}_LEATHER", base_name=f"T{tier}_LEATHER", tier=tier,
            enchantment=0, display_name_pt=f"Couro T{tier}",
            subcategory_code="refinedresources", item_value=2 ** tier, is_tracked=True,
        )
    itens["T1_FACTION_STEPPE_TOKEN_1"] = Item(
        unique_name="T1_FACTION_STEPPE_TOKEN_1", base_name="T1_FACTION_STEPPE_TOKEN_1",
        tier=1, enchantment=0, display_name_pt="Coracao Bestial",
        subcategory_code="cityresources", is_tracked=True,
    )
    session.add_all(itens.values())
    await session.flush()

    for tier in (3, 4):
        base = Recipe(output_item_id=itens[f"T{tier}_LEATHER"].id, variant_index=0,
                      output_quantity=1, focus_cost=tier * 18, silver_cost=0,
                      station_category="leather")
        session.add(base)
        await session.flush()
        session.add_all([
            RecipeMaterial(recipe_id=base.id, item_id=itens[f"T{tier}_HIDE"].id,
                           quantity=2, is_returnable=True),
            RecipeMaterial(recipe_id=base.id, item_id=itens[f"T{tier - 1}_LEATHER"].id,
                           quantity=1, is_returnable=True),
        ])

    com_token = Recipe(output_item_id=itens["T4_LEATHER"].id, variant_index=1,
                       output_quantity=1, focus_cost=72, silver_cost=0,
                       station_category="leather")
    session.add(com_token)
    await session.flush()
    session.add_all([
        RecipeMaterial(recipe_id=com_token.id, item_id=itens["T4_HIDE"].id,
                       quantity=1, is_returnable=True),
        RecipeMaterial(recipe_id=com_token.id, item_id=itens["T1_FACTION_STEPPE_TOKEN_1"].id,
                       quantity=1, is_returnable=False),
        RecipeMaterial(recipe_id=com_token.id, item_id=itens["T3_LEATHER"].id,
                       quantity=1, is_returnable=True),
    ])

    await market_repo.upsert_prices(session, [
        MarketPriceRecord(
            server_id=server.id, location_id=caerleon.id, item_id=itens[nome].id,
            quality=1, sell_price_min=preco, sell_price_min_date=AGORA - timedelta(minutes=5),
            sell_price_max=preco, sell_price_max_date=AGORA - timedelta(minutes=5),
            buy_price_min=preco, buy_price_min_date=AGORA - timedelta(minutes=5),
            buy_price_max=preco, buy_price_max_date=AGORA - timedelta(minutes=5),
            observed_at=AGORA - timedelta(minutes=5), source_id=source.id,
        )
        for nome, preco in PRECOS.items()
    ])
    await session.flush()
    return itens


class TestTabela:
    async def test_uma_linha_por_combinacao_da_familia(self, session, familia):
        resposta = await build_calculator(session, **PADRAO)
        assert [linha.tier_label for linha in resposta.rows] == ["T2.0", "T3.0", "T4.0"]

    async def test_a_ordem_e_a_do_jogo(self, session, familia):
        resposta = await build_calculator(session, **PADRAO)
        tiers = [linha.tier for linha in resposta.rows]
        assert tiers == sorted(tiers)


class TestFormulas:
    async def test_taxa_de_venda_e_imposto_mais_setup(self, session, familia):
        """6,5% no padrao. Uma ordem de venda paga os dois."""
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        assert linha.sale_fee == pytest.approx(linha.gross_revenue * 0.065, rel=1e-6)

    async def test_taxa_da_loja_sai_do_valor_do_item(self, session, familia):
        """`item_value x 0,1125 x F/100 x quantidade`, com iv 16 e F 184."""
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        assert linha.station_fee == pytest.approx(16 * 0.1125 * 1.84 * 100, rel=1e-6)

    async def test_custo_de_producao_soma_as_tres_parcelas(self, session, familia):
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        assert linha.production_cost == pytest.approx(
            linha.material_cost + linha.station_fee + linha.sale_fee, rel=1e-6
        )

    async def test_as_duas_margens_vao_na_resposta(self, session, familia):
        """A nossa e sobre receita; a da planilha e sobre custo de producao."""
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        assert linha.margin_pct == pytest.approx(
            linha.profit / linha.gross_revenue * 100, rel=1e-3
        )
        assert linha.margin_on_cost_pct == pytest.approx(
            linha.profit / linha.production_cost * 100, rel=1e-3
        )


class TestListaDeCompras:
    """Usa o T3, que tem uma variante só.

    No T4 o motor escolhe entre duas receitas, e com o token barato ele escolhe
    a com token — que pede 1 pelego em vez de 2. Fixar a expectativa de
    quantidade ali testaria a escolha de variante, não a lista de compras.
    """

    async def test_o_retorno_reduz_o_que_se_compra(self, session, familia):
        """2 por unidade x 100 unidades x (1 - 0,367) = 126,6 -> 127."""
        resposta = await build_calculator(session, **{**PADRAO, "return_rate": 0.367})
        linha = next(x for x in resposta.rows if x.tier_label == "T3.0")
        pelego = next(m for m in linha.materials if m.item == "T3_HIDE")
        assert pelego.gross_units == 200
        assert pelego.buy_units == 127
        assert pelego.saved_by_return == 73

    async def test_sem_retorno_compra_a_receita_cheia(self, session, familia):
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T3.0")
        pelego = next(m for m in linha.materials if m.item == "T3_HIDE")
        assert pelego.buy_units == 200


class TestVariante:
    async def test_token_barato_vence_e_a_descartada_aparece(self, session, familia):
        """Token a 10: 1 pelego + token (510) bate 2 pelegos (700)."""
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")

        assert linha.variant_label == "com token de faccao"
        assert linha.alternative_label == "sem token"
        assert linha.alternative_cost is not None
        # A escolhida usa 1 pelego; a descartada usaria 2.
        pelego = next(m for m in linha.materials if m.item == "T4_HIDE")
        assert pelego.quantity == 1

    async def test_a_lista_de_compras_segue_a_variante_escolhida(self, session, familia):
        """Não adianta escolher a receita e comprar pela outra."""
        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        token = next(m for m in linha.materials if "TOKEN" in m.item)
        assert token.buy_units == 100
        # Token não volta no retorno: a lista não pode descontá-lo.
        assert token.is_returnable is False


class TestPrecoManual:
    async def test_preco_editado_vence_e_fica_marcado(self, session, familia):
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_LEATHER", 1, 9999, KIND_SELL
        )
        await session.flush()

        resposta = await build_calculator(session, **{**PADRAO, "user_id": USUARIO})
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")

        assert linha.sell_price == 9999
        assert linha.sell_price_is_manual is True
        assert linha.sell_collected_price == 1000

    async def test_sem_usuario_o_editado_nao_vaza(self, session, familia):
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_LEATHER", 1, 9999, KIND_SELL
        )
        await session.flush()

        resposta = await build_calculator(session, **PADRAO)
        linha = next(x for x in resposta.rows if x.tier_label == "T4.0")
        assert linha.sell_price == 1000
        assert linha.sell_price_is_manual is False
