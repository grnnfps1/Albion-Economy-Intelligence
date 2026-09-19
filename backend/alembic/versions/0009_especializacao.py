"""especializacao: pontos de eficiencia de focus por nivel

O custo em Focus vinha cru do dump (`@craftingfocus`), que e o custo de quem
nunca especializou nada. Falta a especializacao, que e o que separa a conta de
quem joga a serio.

    eficiencia = nivel_spec x fce_por_nivel + (mastery + mastery2) x 30
    focus      = focus_base x 0,5 ^ (eficiencia / 10.000)

Como na fase 14, estes numeros **tem** procedencia e por isso entram com valor
em vez de UNKNOWN. Nao sao medicao no jogo -- continuam em `docs/04-taxas.md` --
mas a ancoragem e forte: o dump diz `@craftingfocus = 54` para `T4_LEATHER`, a
comunidade reporta "54 sem spec, 3 com tudo", e 100x250 + 5x100x30 = 40.000
pontos dao 0,5^4 = 6,25%, ou seja 54 -> 3,375. Os tres numeros fecham entre si.

Revision ID: 0009_especializacao
Revises: 0008_taxa_estacao
Create Date: 2026-09-19
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0009_especializacao'
down_revision: str | None = '0008_taxa_estacao'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `config_parameters.source` e varchar(255).
FONTE = (
    "wiki oficial (Specializations, Crafting Focus) + planilha do Albion VIP; "
    "consultado em 19/09/2026; conferido contra @craftingfocus do dump (T4 = 54 "
    "sem spec, 3 com tudo); nao auditado contra codigo da Sandbox"
)

# Pontos de eficiencia por nivel de especializacao, por tipo de peca.
#
# O padrao e `250 + (irmaos x 30)`: o no da 250 ao proprio item e 30 a cada
# irmao do mesmo no. Por isso BAG vale 310 (dois irmaos) e CAPE 370 (quatro), e
# por isso a mao secundaria vale 90 -- ali so entram os 30 mutuos, tres vezes,
# sem os 250 unicos.
#
# REFINING e o unico que a fase 16 liga na interface. Os demais ficam gravados
# com procedencia para a fase que ligar craft de equipamento; ate la o craft
# calcula com spec 0, que e o lado conservador de errar.
FCE_POR_NIVEL = {
    "REFINING": 250,
    "MAIN": 250,
    "2H": 250,
    "OFF_PRIMARY": 250,
    "OFF_SECONDARY": 90,
    "BAG": 310,
    "CAPE": 370,
    "GATHERER": 250,
    "FOOD": 250,
}

# As cinco familias de refino que a interface expoe, uma por linha de recurso.
# Item a item seriam centenas de campos; por familia sao cinco.
FAMILIAS_DE_REFINO = ["LEATHER", "CLOTH", "PLANKS", "METALBAR", "STONEBLOCK"]

PARAMETROS = [
    (
        "crafting.focus_efficiency.halving_points",
        10000,
        "Pontos de focus cost efficiency que cortam o custo pela metade.",
    ),
    (
        "crafting.focus_efficiency.per_mastery_level",
        30,
        "Pontos de eficiencia por nivel de maestria, em toda a categoria.",
    ),
    (
        "crafting.focus_efficiency.per_spec_level",
        FCE_POR_NIVEL,
        "Pontos de eficiencia por nivel de especializacao, por tipo de peca. "
        "O padrao e 250 + (irmaos do no x 30).",
    ),
    (
        "crafting.spec_families",
        FAMILIAS_DE_REFINO,
        "Familias de refino que a interface pede o nivel de spec. Por familia e "
        "nao item a item: item a item seriam centenas de campos.",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    for key, value, description in PARAMETROS:
        bind.execute(
            sa.text(
                "INSERT INTO config_parameters (key, value, scope, description, source) "
                "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
                "ON CONFLICT (key) DO UPDATE SET "
                "value = EXCLUDED.value, description = EXCLUDED.description, "
                "source = EXCLUDED.source"
            ),
            {
                "key": key,
                "value": json.dumps(value),
                "description": description,
                "source": FONTE,
            },
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM config_parameters WHERE key IN "
            "('crafting.focus_efficiency.halving_points', "
            " 'crafting.focus_efficiency.per_mastery_level', "
            " 'crafting.focus_efficiency.per_spec_level', "
            " 'crafting.spec_families')"
        )
    )
