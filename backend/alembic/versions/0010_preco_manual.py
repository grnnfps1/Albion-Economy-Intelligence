"""preco manual: sobrescrita do usuario sobre a cotacao coletada

Cotacao comunitaria fica velha, e mercado pouco visitado pode nao ter cotacao
nenhuma. Quem esta com o jogo aberto sabe o preco melhor que a coleta.

`kind` distingue as duas pontas pela consequencia, nao pelo nome do campo da
API:

    COMPRA  o que voce paga     -> sobrescreve sell_price_min
    VENDA   o que voce recebe   -> sobrescreve buy_price_max

`user_id` e o `discord_id` da sessao: nao ha tabela de contas ainda, e a fonte
da verdade do acesso ja e o Discord. Quando contas existirem, a coluna vira FK
sem mudar a semantica.

Revision ID: 0010_preco_manual
Revises: 0009_especializacao
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0010_preco_manual'
down_revision: str | None = '0009_especializacao'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manual_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("server_id", sa.SmallInteger(), nullable=False),
        sa.Column("location_id", sa.SmallInteger(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quality", sa.SmallInteger(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quality BETWEEN 1 AND 5", name="ck_manual_prices_quality"),
        # Zero nao e preco, e ausencia -- e ausencia se apaga a linha.
        sa.CheckConstraint("price > 0", name="ck_manual_prices_price_positivo"),
        sa.CheckConstraint("kind IN ('COMPRA', 'VENDA')", name="ck_manual_prices_kind"),
        sa.UniqueConstraint(
            "user_id", "server_id", "location_id", "item_id", "quality", "kind",
            name="uq_manual_prices_chave",
        ),
    )
    op.create_index(
        "ix_manual_prices_lookup", "manual_prices", ["user_id", "server_id", "item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_manual_prices_lookup", table_name="manual_prices")
    op.drop_table("manual_prices")
