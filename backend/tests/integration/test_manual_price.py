"""Preço manual: quando vence o coletado e quando envelhece junto.

A pergunta que estes testes cercam: o preço que o usuário digitou é autoridade
ou é só mais uma cotação? Resposta: é autoridade **enquanto for fresco**, e a
tela precisa dizer qual dos dois está em uso.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.aodp.normalization import MarketPriceRecord
from app.core.config import get_settings
from app.models.catalog import Item
from app.models.manual_price import KIND_BUY, KIND_SELL
from app.models.reference import DataSource, Location, Server
from app.repositories import manual_prices as manual_repo
from app.repositories import market as market_repo
from app.services.manual_price_service import load_manual_overlay
from app.services.market_service import to_price_out

pytestmark = pytest.mark.asyncio

AGORA = datetime.now(UTC)
USUARIO = "discord-42"


@pytest.fixture
async def cenario(session):
    server = Server(code="west", display_name="Americas", aodp_base_url="https://x")
    caerleon = Location(aodp_name="Caerleon", slug="caerleon",
                        display_name="Caerleon", kind="royal_city")
    source = DataSource(code="aodp", display_name="AODP", is_community_sourced=True)
    planks = Item(unique_name="T4_PLANKS", base_name="T4_PLANKS", tier=4, enchantment=0,
                  display_name_pt="Tábuas de Pinho", subcategory_code="refinedresources",
                  item_value=16, is_tracked=True)
    session.add_all([server, caerleon, source, planks])
    await session.flush()

    await market_repo.upsert_prices(session, [
        MarketPriceRecord(
            server_id=server.id, location_id=caerleon.id, item_id=planks.id, quality=1,
            sell_price_min=1000, sell_price_min_date=AGORA - timedelta(hours=2),
            sell_price_max=1100, sell_price_max_date=AGORA - timedelta(hours=2),
            buy_price_min=800, buy_price_min_date=AGORA - timedelta(hours=2),
            buy_price_max=900, buy_price_max_date=AGORA - timedelta(hours=2),
            observed_at=AGORA - timedelta(hours=2), source_id=source.id,
        )
    ])
    await session.flush()
    return {"server": server, "location": caerleon, "item": planks}


async def linha(session, manual=None):
    rows, _ = await market_repo.search_prices(session, server_code="west", limit=10)
    price, item, location = rows[0]
    return to_price_out(price, item, location, AGORA, get_settings(), None, manual)


class TestVenceOColetado:
    async def test_preco_manual_de_compra_sobrescreve_o_que_voce_paga(self, session, cenario):
        """COMPRA é `sell_price_min`: a ordem de venda mais barata."""
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        overlay = await load_manual_overlay(session, USUARIO, "west", now=AGORA)
        out = await linha(session, overlay)

        assert out.sell_min.value == 1234
        assert out.sell_min.is_manual is True
        # O coletado vai junto: é o que permite perceber um zero a mais.
        assert out.sell_min.collected_value == 1000

    async def test_preco_manual_de_venda_sobrescreve_o_que_voce_recebe(self, session, cenario):
        """VENDA é `buy_price_max`. Trocar as duas pontas inverte o lucro."""
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 950, KIND_SELL
        )
        await session.flush()

        overlay = await load_manual_overlay(session, USUARIO, "west", now=AGORA)
        out = await linha(session, overlay)

        assert out.buy_max.value == 950
        assert out.buy_max.is_manual is True
        # A outra ponta não foi tocada.
        assert out.sell_min.value == 1000
        assert out.sell_min.is_manual is False

    async def test_a_idade_exibida_e_a_de_quando_foi_informado(self, session, cenario):
        """Não a da cotação que ele substituiu.

        A coleta é de 2 horas atrás; o preço manual é de agora. Herdar a idade
        do coletado faria um preço fresco parecer velho.
        """
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        overlay = await load_manual_overlay(session, USUARIO, "west", now=AGORA)
        out = await linha(session, overlay)

        assert out.sell_min.age_seconds < 60
        assert out.sell_min.freshness == "ATUALIZADO"


class TestEnvelhece:
    async def test_preco_manual_velho_nao_vence_mais(self, session, cenario):
        """Preço manual velho é tão perigoso quanto cotação velha.

        Pior, até: parece autoridade. Passado o limite de frescor, o coletado
        volta.
        """
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        limite = get_settings().freshness_stale_seconds
        depois = AGORA + timedelta(seconds=limite + 60)
        overlay = await load_manual_overlay(session, USUARIO, "west", now=depois)
        out = await linha(session, overlay)

        assert out.sell_min.value == 1000
        assert out.sell_min.is_manual is False

    async def test_manual_expirado_e_dito_e_nao_ignorado_em_silencio(self, session, cenario):
        """Senão o usuário acha que o preço que ele informou continua valendo."""
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        limite = get_settings().freshness_stale_seconds
        overlay = await load_manual_overlay(
            session, USUARIO, "west", now=AGORA + timedelta(seconds=limite + 60)
        )
        out = await linha(session, overlay)

        assert out.sell_min.manual_expired is True

    async def test_reinformar_renova_a_idade(self, session, cenario):
        """Quem reinforma acabou de olhar o mercado."""
        antigo = await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()
        primeiro = antigo.created_at

        novo = await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 4321, KIND_BUY
        )
        await session.flush()

        assert novo.price == 4321
        assert novo.created_at >= primeiro


class TestIsolamento:
    async def test_preco_de_um_usuario_nao_vaza_para_outro(self, session, cenario):
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        outro = await load_manual_overlay(session, "discord-99", "west", now=AGORA)
        assert outro.empty is True
        assert (await linha(session, outro)).sell_min.value == 1000

    async def test_sem_usuario_o_comportamento_e_o_de_antes(self, session, cenario):
        """Desenvolvimento local roda sem login; nada pode quebrar por isso."""
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()

        vazio = await load_manual_overlay(session, None, "west", now=AGORA)
        assert vazio.empty is True
        assert (await linha(session, vazio)).sell_min.value == 1000


class TestEscrita:
    async def test_apagar_devolve_o_coletado(self, session, cenario):
        await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 1234, KIND_BUY
        )
        await session.flush()
        removidos = await manual_repo.remove(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, KIND_BUY
        )
        await session.flush()

        assert removidos == 1
        overlay = await load_manual_overlay(session, USUARIO, "west", now=AGORA)
        assert (await linha(session, overlay)).sell_min.value == 1000

    async def test_item_inexistente_nao_grava_linha_orfa(self, session, cenario):
        resultado = await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "NAO_EXISTE", 1, 100, KIND_BUY
        )
        assert resultado is None

    async def test_kind_invalido_e_recusado(self, session, cenario):
        resultado = await manual_repo.upsert(
            session, USUARIO, "west", "caerleon", "T4_PLANKS", 1, 100, "QUALQUER"
        )
        assert resultado is None
