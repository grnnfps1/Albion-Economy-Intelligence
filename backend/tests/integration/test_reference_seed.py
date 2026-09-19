"""Conteúdo do seed de referência.

Roda contra o banco criado pelas MIGRATIONS (não pelos modelos), porque o que se
está verificando aqui é o resultado de `alembic upgrade head`.
"""

import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio

MIGRATED_DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture
async def migrated_connection():
    if not MIGRATED_DATABASE_URL:
        pytest.skip("DATABASE_URL não definida; seed só é verificável no banco migrado")
    engine = create_async_engine(MIGRATED_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1 FROM alembic_version"))
            yield connection
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"banco migrado indisponível: {type(exc).__name__}")
    finally:
        await engine.dispose()


async def test_tres_servidores_com_hosts_do_aodp(migrated_connection):
    rows = (
        await migrated_connection.execute(
            text("SELECT code, aodp_base_url FROM servers ORDER BY code")
        )
    ).all()
    assert dict(rows) == {
        "east": "https://east.albion-online-data.com",
        "europe": "https://europe.albion-online-data.com",
        "west": "https://west.albion-online-data.com",
    }


async def test_black_market_nao_e_cidade(migrated_connection):
    """Requisito 31: Black Market existe, mas com kind próprio."""
    kind = await migrated_connection.scalar(
        text("SELECT kind FROM locations WHERE aodp_name = 'Black Market'")
    )
    assert kind == "black_market"

    cidades = await migrated_connection.scalar(
        text("SELECT count(*) FROM locations WHERE kind = 'royal_city'")
    )
    assert cidades == 7


async def test_nomes_de_local_batem_com_a_string_do_aodp(migrated_connection):
    """A chave de lookup é a string exata da API, com espaço e tudo."""
    nomes = set(
        (await migrated_connection.execute(text("SELECT aodp_name FROM locations"))).scalars()
    )
    assert "Fort Sterling" in nomes
    assert "Black Market" in nomes


async def test_fonte_aodp_marcada_como_comunitaria(migrated_connection):
    community = await migrated_connection.scalar(
        text("SELECT is_community_sourced FROM data_sources WHERE code = 'aodp'")
    )
    assert community is True


async def test_taxas_de_mercado_tem_valor_e_procedencia(migrated_connection):
    """Requisito 52: número **sempre** com procedência; nunca um com `UNKNOWN`.

    A guarda mudou de forma na fase 21 e não de espírito. Antes era "as taxas
    de mercado seguem NULL", porque nenhuma havia sido medida. Agora as quatro
    têm valor — três de medição no jogo e uma de confirmação do usuário — e o
    que se guarda é o invariante que sempre valeu: **valor sem fonte é chute**.

    O teste continua caindo se alguém preencher um número sem dizer de onde
    veio. Foi exatamente o que ele fez quando as medições entraram.
    """
    rows = (
        await migrated_connection.execute(
            text("SELECT key, value, source FROM config_parameters WHERE key LIKE 'market.%'")
        )
    ).all()
    assert rows, "parâmetros de taxa deveriam existir no seed"

    for key, value, source in rows:
        assert value is not None, f"{key} ficou sem valor"
        assert 0 < float(value) < 1, f"{key} fora da faixa de uma taxa"
        assert source != "UNKNOWN", f"{key} tem número sem procedência"
        assert "19/09/2026" in source, f"{key} não diz quando foi obtido"


async def test_o_imposto_sem_premium_nao_foi_derivado_do_com_premium(migrated_connection):
    """As duas procedências são diferentes, e a tabela precisa guardar isso.

    4% tem notificação do jogo discriminando preço, taxa e recebido. 8% veio de
    confirmação do usuário. São 2×, e é justamente por isso que a distinção
    importa: se alguém tivesse dobrado o primeiro para obter o segundo, seria um
    chute com cara de medição — e nada na tabela denunciaria.
    """
    fontes = dict(
        (
            await migrated_connection.execute(
                text(
                    "SELECT key, source FROM config_parameters "
                    "WHERE key IN ('market.sales_tax_pct.premium', "
                    "'market.sales_tax_pct.standard')"
                )
            )
        ).all()
    )
    premium = fontes["market.sales_tax_pct.premium"]
    standard = fontes["market.sales_tax_pct.standard"]

    assert "medicao" in premium
    assert "notificacao" in premium
    assert premium != standard, "procedências diferentes não podem ter a mesma string"
    assert "nao derivado" in standard


async def test_bonus_de_retorno_tem_valor_e_procedencia(migrated_connection):
    """Os componentes da fórmula têm número — e por isso **precisam** ter fonte.

    A regra nunca foi "tudo NULL": era "nenhum número sem procedência". Estes
    são os bônus oficiais, e a fórmula que os converte em taxa foi conferida
    contra os cenários publicados. A string de `source` diz as duas coisas.

    Substituiu a guarda da matriz de quatro células da fase 14: a matriz saiu
    na fase 20, quando a tabela virou fórmula.
    """
    rows = (
        await migrated_connection.execute(
            text(
                "SELECT key, value, source FROM config_parameters "
                "WHERE key LIKE '%.return_bonus.%'"
            )
        )
    ).all()
    assert len(rows) == 4, "base de cidade, refino, craft e foco"

    for key, value, source in rows:
        assert value is not None, f"{key} ficou sem valor"
        assert 0 < float(value) < 1, f"{key} fora da faixa de um bônus"
        assert source != "UNKNOWN", f"{key} tem número sem procedência"
        assert "consultado em" in source, f"{key} não diz a data da consulta"
        assert "verificad" in source, f"{key} não diz como foi conferido"


async def test_a_matriz_de_valores_fixos_saiu(migrated_connection):
    """A fase 20 removeu as oito células.

    Mantê-las convidaria alguém a preencher um valor que o motor não lê mais —
    e a divergir em silêncio da fórmula.
    """
    rows = (
        await migrated_connection.execute(
            text("SELECT key FROM config_parameters WHERE key LIKE '%.return_rate.%'")
        )
    ).all()
    assert rows == []


async def test_bonus_de_refino_cobre_as_cinco_linhas_de_recurso(migrated_connection):
    """Cada cidade leva o bruto e o refinado da mesma linha.

    E as cinco linhas precisam estar todas lá: faltar uma faria o material
    daquela linha cair no retorno base em qualquer cidade, sem ninguém notar.
    """
    value, source = (
        await migrated_connection.execute(
            text(
                "SELECT value, source FROM config_parameters "
                "WHERE key = 'refining.city_bonus_resources'"
            )
        )
    ).one()

    assert source != "UNKNOWN", "mapeamento com valor precisa de procedência"
    mapa = value if isinstance(value, dict) else json.loads(value)

    esperado = {
        "fort-sterling": ["WOOD", "PLANKS"],
        "lymhurst": ["FIBER", "CLOTH"],
        "bridgewatch": ["ROCK", "STONEBLOCK"],
        "martlock": ["HIDE", "LEATHER"],
        "thetford": ["ORE", "METALBAR"],
    }
    for cidade, familias in esperado.items():
        assert mapa[cidade] == familias, f"{cidade} com a linha de recurso errada"

    # Caerleon entra com lista vazia: é afirmação de "sem bônus", não lacuna.
    assert mapa["caerleon"] == []

    # Nenhuma família em duas cidades — seria bônus duplicado.
    todas = [f for familias in mapa.values() for f in familias]
    assert len(todas) == len(set(todas))


async def test_pesos_do_score_sao_configuraveis(migrated_connection):
    """Requisito 20: os pesos ficam em configuração, não dentro da fórmula."""
    weights = await migrated_connection.scalar(
        text("SELECT value FROM config_parameters WHERE key = 'score.weights'")
    )
    assert set(weights) == {
        "profit", "margin", "roi", "freshness", "liquidity", "trend", "distance", "risk"
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-9
