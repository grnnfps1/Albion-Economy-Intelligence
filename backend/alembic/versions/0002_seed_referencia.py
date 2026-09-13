"""seed de referencia: servidores, locais, fontes de dado e parametros

Revision ID: 0002_seed_referencia
Revises: 0001_schema_inicial
Create Date: 2026-09-12

Seed idempotente. Rodar `alembic upgrade head` duas vezes não duplica nada e não
sobrescreve valor que um operador tenha ajustado depois (ON CONFLICT DO NOTHING).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_referencia"
down_revision: str | None = "0001_schema_inicial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hosts verificados em 2026-09-12 contra pow.albion-online-data.com/api.
SERVERS = [
    ("west", "Americas (West)", "https://west.albion-online-data.com"),
    ("east", "Asia (East)", "https://east.albion-online-data.com"),
    ("europe", "Europe", "https://europe.albion-online-data.com"),
]

# `aodp_name` é a string exata que o AODP devolve no campo `city` / `location`.
# Todas foram observadas em respostas reais da API -- não são transcrições da
# documentação.
LOCATIONS = [
    ("Caerleon", "caerleon", "Caerleon", "royal_city", True),
    ("Bridgewatch", "bridgewatch", "Bridgewatch", "royal_city", True),
    ("Lymhurst", "lymhurst", "Lymhurst", "royal_city", True),
    ("Fort Sterling", "fort-sterling", "Fort Sterling", "royal_city", True),
    ("Martlock", "martlock", "Martlock", "royal_city", True),
    ("Thetford", "thetford", "Thetford", "royal_city", True),
    ("Brecilien", "brecilien", "Brecilien", "royal_city", True),
    ("Black Market", "black-market", "Black Market", "black_market", True),
]

DATA_SOURCES = [
    (
        "aodp",
        "Albion Online Data Project",
        "https://west.albion-online-data.com",
        True,
        False,
        "Coleta comunitária: o dado existe porque algum jogador abriu aquele mercado "
        "no jogo com o client de coleta rodando. Nenhuma cotação é garantida.",
    ),
    (
        "ao-bin-dumps",
        "ao-data/ao-bin-dumps",
        "https://raw.githubusercontent.com/ao-data/ao-bin-dumps",
        False,
        False,
        "Dump oficial do cliente do jogo. Fonte do catálogo de itens, pesos, "
        "categorias e receitas.",
    ),
    ("manual", "Entrada manual", None, False, False, "Valor informado por um operador."),
    (
        "mock",
        "Dado sintético",
        None,
        False,
        True,
        "Somente desenvolvimento. A aplicação recusa subir em production com mock ativo.",
    ),
]

# value NULL + source UNKNOWN = a estrutura existe, o número ainda não foi
# verificado. Quem consumir precisa tratar como desconhecido e não calcular
# (requisito 52). Preencher com fonte citada quando a fase de cálculo chegar.
CONFIG_UNVERIFIED = [
    ("market.sell_order_setup_fee_pct", "taxa de criação de ordem de venda", "global"),
    ("market.sales_tax_pct.premium", "imposto de venda com Premium", "global"),
    ("market.sales_tax_pct.standard", "imposto de venda sem Premium", "global"),
    ("crafting.station_fee_formula", "fórmula da taxa de estação de crafting", "global"),
    ("crafting.return_rate.base", "taxa de retorno de material sem Focus", "global"),
    ("crafting.return_rate.focus", "taxa de retorno de material com Focus", "global"),
    ("refining.return_rate.base", "taxa de retorno de refino sem Focus", "global"),
    ("refining.return_rate.focus", "taxa de retorno de refino com Focus", "global"),
]

# Decisões do produto, não fatos do jogo: podem ser definidas agora.
CONFIG_PRODUCT = [
    (
        "freshness.fresh_seconds",
        900,
        "Até quantos segundos um preço é exibido como ATUALIZADO",
    ),
    (
        "freshness.stale_seconds",
        21600,
        "Até quantos segundos um preço é DESATUALIZADO; acima disso é ANTIGO",
    ),
    (
        "score.weights",
        {
            "profit": 0.25,
            "margin": 0.20,
            "roi": 0.15,
            "freshness": 0.15,
            "liquidity": 0.15,
            "trend": 0.05,
            "distance": 0.03,
            "risk": 0.02,
        },
        "Pesos do score de oportunidade. Configuráveis por definição (requisito 20); "
        "estes são o ponto de partida e serão calibrados com dado real na fase 6.",
    ),
    (
        "score.bands",
        {"ruim": [0, 39], "moderada": [40, 59], "boa": [60, 74], "muito_boa": [75, 89],
         "excelente": [90, 100]},
        "Faixas de classificação do score (requisito 20).",
    ),
    (
        "collector.min_freshness_to_publish_seconds",
        21600,
        "Oportunidade calculada sobre preço mais velho que isto não é publicada (risco R1).",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "INSERT INTO servers (code, display_name, aodp_base_url, active) "
            "VALUES (:code, :display_name, :url, true) ON CONFLICT (code) DO NOTHING"
        ),
        [{"code": c, "display_name": d, "url": u} for c, d, u in SERVERS],
    )

    conn.execute(
        sa.text(
            "INSERT INTO locations "
            "(aodp_name, slug, display_name, kind, supports_buy_orders, active) "
            "VALUES (:aodp_name, :slug, :display_name, :kind, :buy, true) "
            "ON CONFLICT (aodp_name) DO NOTHING"
        ),
        [
            {"aodp_name": a, "slug": s, "display_name": d, "kind": k, "buy": b}
            for a, s, d, k, b in LOCATIONS
        ],
    )

    conn.execute(
        sa.text(
            "INSERT INTO data_sources "
            "(code, display_name, base_url, is_community_sourced, is_mock, notes) "
            "VALUES (:code, :display_name, :url, :community, :mock, :notes) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        [
            {
                "code": c,
                "display_name": d,
                "url": u,
                "community": comm,
                "mock": mock,
                "notes": notes,
            }
            for c, d, u, comm, mock, notes in DATA_SOURCES
        ],
    )

    insert_config = sa.text(
        "INSERT INTO config_parameters (key, value, scope, description, source) "
        "VALUES (:key, CAST(:value AS jsonb), :scope, :description, :source) "
        "ON CONFLICT (key) DO NOTHING"
    )

    conn.execute(
        insert_config,
        [
            {
                "key": key,
                "value": "null",
                "scope": scope,
                "description": description,
                "source": "UNKNOWN",
            }
            for key, description, scope in CONFIG_UNVERIFIED
        ],
    )

    import json

    conn.execute(
        insert_config,
        [
            {
                "key": key,
                "value": json.dumps(value),
                "scope": "global",
                "description": description,
                "source": "decisão do projeto",
            }
            for key, value, description in CONFIG_PRODUCT
        ],
    )


def downgrade() -> None:
    """Remove o seed.

    Falha com ForeignKeyViolation se já houver dado de mercado apontando para
    `data_sources` ou `servers` -- e isso é o comportamento certo. O RESTRICT
    existe para impedir que uma reversão de schema apague em silêncio a
    procedência de preços já coletados. Para reverter de verdade, limpe
    `market_prices`, `market_history` e `gold_prices` antes.
    """
    conn = op.get_bind()
    keys = [key for key, _, _ in CONFIG_UNVERIFIED] + [key for key, _, _ in CONFIG_PRODUCT]
    conn.execute(
        sa.text("DELETE FROM config_parameters WHERE key = ANY(:keys)"), {"keys": keys}
    )
    conn.execute(
        sa.text("DELETE FROM data_sources WHERE code = ANY(:codes)"),
        {"codes": [c for c, *_ in DATA_SOURCES]},
    )
    conn.execute(
        sa.text("DELETE FROM locations WHERE aodp_name = ANY(:names)"),
        {"names": [a for a, *_ in LOCATIONS]},
    )
    conn.execute(
        sa.text("DELETE FROM servers WHERE code = ANY(:codes)"),
        {"codes": [c for c, *_ in SERVERS]},
    )
