"""taxa de estacao derivada do valor do item

A taxa da estação deixa de ser um número fixo por execução e passa a ser
derivada, como o jogo a cobra: por **nutrição consumida**.

    nutricao = item_value × 0,1125
    taxa     = nutricao × (prata_por_100_nutricao ÷ 100)

Duas coisas entram aqui:

1. `items.item_value`, alimentado por `@itemvalue` do dump. É o que escala com
   tier e encantamento, e é a razão de um valor fixo errar por duas ordens de
   grandeza entre T2 e T8.
2. Os dois parâmetros que substituem `crafting.station_fee_formula`:
   `crafting.nutrition_per_item_value` (constante da Sandbox, com fonte) e
   `crafting.station_fee_per_100_nutrition` (o número que o dono da estação
   anuncia -- é do usuário, e fica NULL/UNKNOWN aqui).

A distinção entre os dois segue a regra da fase 14: número com procedência é
gravado com a procedência; número que só o usuário tem continua UNKNOWN.

Revision ID: 0008_taxa_estacao
Revises: 0007_bonus_refino
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0008_taxa_estacao'
down_revision: str | None = '0007_bonus_refino'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Anúncio de patch da própria Sandbox, não engenharia reversa da comunidade.
# É a diferença entre este número e os da matriz de retorno.
# `config_parameters.source` e varchar(255): a procedencia precisa caber.
FONTE_NUTRICAO = (
    "Sandbox Interactive, anuncio do patch Lands Awakened: 'Nutrition Cost = "
    "Item Value * 0.1125' e 'Usage Fees are now set as an amount of Silver per "
    "100 Nutrition consumed'; consultado em 19/09/2026; anuncio oficial, nao "
    "engenharia reversa"
)

DESC_NUTRICAO = (
    "Nutricao consumida por unidade de item value. Constante do jogo, nao "
    "preferencia: quem varia e a prata por 100 de nutricao, que o dono da "
    "estacao define."
)

DESC_TAXA = (
    "Prata por 100 de nutricao cobrada pela estacao. E o numero que o jogador "
    "le na tela da estacao. Varia por cidade, por estacao e por hora, entao o "
    "padrao do banco e NULL: quem informa e o usuario."
)


def upgrade() -> None:
    op.add_column(
        "items", sa.Column("item_value", sa.Numeric(precision=12, scale=4), nullable=True)
    )

    bind = op.get_bind()

    # A constante tem fonte oficial: entra com valor.
    bind.execute(
        sa.text(
            "INSERT INTO config_parameters (key, value, scope, description, source) "
            "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
            "ON CONFLICT (key) DO UPDATE SET "
            "value = EXCLUDED.value, description = EXCLUDED.description, "
            "source = EXCLUDED.source"
        ),
        {
            "key": "crafting.nutrition_per_item_value",
            "value": "0.1125",
            "description": DESC_NUTRICAO,
            "source": FONTE_NUTRICAO,
        },
    )

    # A taxa é do usuário: estrutura existe, valor não. Mesmo tratamento do
    # imposto de venda.
    bind.execute(
        sa.text(
            "INSERT INTO config_parameters (key, value, scope, description, source) "
            "VALUES (:key, 'null'::jsonb, 'global', :description, 'UNKNOWN') "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"key": "crafting.station_fee_per_100_nutrition", "description": DESC_TAXA},
    )

    # A chave antiga descreveria uma taxa por execução, que não existe mais.
    # Deixá-la no banco convidaria alguém a preenchê-la e a ver o número ser
    # ignorado em silêncio.
    bind.execute(
        sa.text("DELETE FROM config_parameters WHERE key = 'crafting.station_fee_formula'")
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO config_parameters (key, value, scope, description, source) "
            "VALUES ('crafting.station_fee_formula', 'null'::jsonb, 'global', "
            ":description, 'UNKNOWN') ON CONFLICT (key) DO NOTHING"
        ),
        {"description": "formula da taxa de estacao de crafting"},
    )
    bind.execute(
        sa.text(
            "DELETE FROM config_parameters WHERE key IN "
            "('crafting.nutrition_per_item_value', "
            " 'crafting.station_fee_per_100_nutrition')"
        )
    )
    op.drop_column("items", "item_value")
