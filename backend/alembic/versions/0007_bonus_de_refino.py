"""bônus de refino por cidade

Fecha o `UNKNOWN` deixado pela 0006. O bônus de refino segue o **recurso**, e o
recurso segue o bioma da cidade — por isso o mapeamento é por família de recurso
e não por item.

As famílias são os dez tokens reais do catálogo, conferidos antes de gravar:
`WOOD`/`PLANKS`, `FIBER`/`CLOTH`, `ROCK`/`STONEBLOCK`, `HIDE`/`LEATHER`,
`ORE`/`METALBAR`. Cada cidade leva o bruto e o refinado da mesma linha.

Caerleon fica de fora dos cinco básicos: ela não tem bônus de refino.

Revision ID: 0007_bonus_refino
Revises: 0006_matriz_retorno
Create Date: 2026-09-16
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0007_bonus_refino'
down_revision: str | None = '0006_matriz_retorno'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FONTE = (
    "guia oficial de refino da Albion Online + tabelas de bonus locais de "
    "albiononlinegrind; consultado em 16/09/2026; mesma procedencia da matriz de "
    "retorno; nao auditado contra codigo da Sandbox"
)

# Cidade -> famílias de recurso com bônus de refino. Bruto e refinado juntos:
# quem refina madeira em Fort Sterling parte de `WOOD` e entrega `PLANKS`.
RECURSOS_POR_CIDADE = {
    "fort-sterling": ["WOOD", "PLANKS"],
    "lymhurst": ["FIBER", "CLOTH"],
    "bridgewatch": ["ROCK", "STONEBLOCK"],
    "martlock": ["HIDE", "LEATHER"],
    "thetford": ["ORE", "METALBAR"],
    # Sem bônus nos cinco básicos. A lista vazia é afirmação, não lacuna: é
    # diferente de a cidade não estar no mapa.
    "caerleon": [],
}


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE config_parameters "
            "SET value = CAST(:value AS jsonb), source = :source, description = :description "
            "WHERE key = 'refining.city_bonus_resources'"
        ),
        {
            "value": json.dumps(RECURSOS_POR_CIDADE),
            "source": FONTE,
            "description": "Familias de recurso com bonus de refino, por cidade.",
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE config_parameters SET value = 'null'::jsonb, source = 'UNKNOWN' "
            "WHERE key = 'refining.city_bonus_resources'"
        )
    )
