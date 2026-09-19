"""retorno vira formula: RRR = B / (1 + B)

A matriz de quatro celulas por atividade da fase 14 era uma tabela de valores
medidos. Aqui ela vira a **formula que os gera**, com os bonus oficiais como
componentes:

    base de cidade   +18%   (ilha = 0)
    refino da cidade +40%
    craft da cidade  +15%
    foco             +59%

    RRR = B / (1 + B)

Isso resolve o impasse do item 6 de docs/04-taxas.md: a doc oficial fala em
+40% e a comunidade mede 36,7%. Os dois estavam certos e mediam coisas
diferentes -- 0,58/1,58 = 0,367. O bonus e o que a estacao soma; o retorno e a
fracao que volta.

As chaves antigas da matriz saem: mante-las convidaria alguem a preencher um
valor que o motor nao le mais.

Revision ID: 0011_formula_retorno
Revises: 0010_preco_manual
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0011_formula_retorno'
down_revision: str | None = '0010_preco_manual'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `config_parameters.source` e varchar(255).
FONTE = (
    "bonus oficiais da documentacao do jogo; formula RRR = B/(1+B) e a "
    "decomposicao verificadas contra os cinco cenarios publicados, todos "
    "fechando na casa decimal; consultado em 19/09/2026"
)

COMPONENTES = [
    (
        "crafting.return_bonus.city_base",
        0.18,
        "Bonus base de qualquer cidade real. Ilha nao tem: la o componente e 0.",
    ),
    (
        "refining.return_bonus.city",
        0.40,
        "Bonus de refino da cidade do recurso. Soma-se a base.",
    ),
    (
        "crafting.return_bonus.city",
        0.15,
        "Bonus de craft da cidade da familia do item. Soma-se a base.",
    ),
    (
        "crafting.return_bonus.focus",
        0.59,
        "Bonus de usar Focus. Soma-se aos demais antes da conversao.",
    ),
]

# A matriz de valores fixos da fase 14. Sai porque o motor nao a le mais.
MATRIZ_ANTIGA = [
    "refining.return_rate.bonus.base",
    "refining.return_rate.bonus.focus",
    "refining.return_rate.base",
    "refining.return_rate.focus",
    "crafting.return_rate.bonus.base",
    "crafting.return_rate.bonus.focus",
    "crafting.return_rate.base",
    "crafting.return_rate.focus",
]


def upgrade() -> None:
    bind = op.get_bind()
    for key, value, description in COMPONENTES:
        bind.execute(
            sa.text(
                "INSERT INTO config_parameters (key, value, scope, description, source) "
                "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
                "ON CONFLICT (key) DO UPDATE SET "
                "value = EXCLUDED.value, description = EXCLUDED.description, "
                "source = EXCLUDED.source"
            ),
            {"key": key, "value": str(value), "description": description, "source": FONTE},
        )

    bind.execute(
        sa.text("DELETE FROM config_parameters WHERE key = ANY(:keys)"),
        {"keys": MATRIZ_ANTIGA},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM config_parameters WHERE key = ANY(:keys)"),
        {"keys": [k for k, _v, _d in COMPONENTES]},
    )
    # A matriz volta vazia: os valores dela eram da fase 14 e o downgrade nao
    # tem como saber se ainda sao os que o operador quer.
    for key in MATRIZ_ANTIGA:
        bind.execute(
            sa.text(
                "INSERT INTO config_parameters (key, value, scope, description, source) "
                "VALUES (:key, 'null'::jsonb, 'global', :description, 'UNKNOWN') "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key, "description": "celula da matriz de retorno (fase 14)"},
        )
