"""ilha como local de producao

A ilha entra no cadastro de locais com `kind = 'island'`, que e o que a
politica de retorno le para zerar a base de cidade: quem refina em ilha tem
**0% sem Focus e 37,1% com**.

Duas colunas contam a historia dela, e as duas sao `false`:

- `active = false` -- ilha nao entra na varredura do collector;
- `supports_buy_orders = false` -- nao ha ordem de compra em ilha.

Ilha **nao tem mercado**. O AODP nao publica preco de ilha porque nao existe
ordem la. Quem produz na ilha compra os materiais numa cidade e carrega. Por
isso ela e escolha de *onde produzir*, e nao de *onde comprar* -- as duas
coisas sao de fato diferentes, e confundi-las faria a tela pedir cotacao de um
mercado que nao existe.

O check de `kind` precisa ser estendido: ilha nao e cidade real nem zona de
descanso, e forcar 'other' apagaria a informacao que a politica de retorno le.

Revision ID: 0012_ilha
Revises: 0011_formula_retorno
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0012_ilha'
down_revision: str | None = '0011_formula_retorno'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_NOVOS = "'royal_city', 'black_market', 'portal_city', 'rest_zone', 'island', 'other'"
KINDS_ANTIGOS = "'royal_city', 'black_market', 'portal_city', 'rest_zone', 'other'"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE locations DROP CONSTRAINT ck_locations_kind"))
    bind.execute(
        sa.text(
            f"ALTER TABLE locations ADD CONSTRAINT ck_locations_kind "
            f"CHECK (kind IN ({KINDS_NOVOS}))"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO locations "
            "(aodp_name, slug, display_name, kind, active, supports_buy_orders) "
            "VALUES (:aodp_name, :slug, :display_name, 'island', false, false) "
            "ON CONFLICT (slug) DO NOTHING"
        ),
        {"aodp_name": "Island", "slug": "island", "display_name": "Ilha"},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM locations WHERE slug = 'island'"))
    bind.execute(sa.text("ALTER TABLE locations DROP CONSTRAINT ck_locations_kind"))
    bind.execute(
        sa.text(
            f"ALTER TABLE locations ADD CONSTRAINT ck_locations_kind "
            f"CHECK (kind IN ({KINDS_ANTIGOS}))"
        )
    )
