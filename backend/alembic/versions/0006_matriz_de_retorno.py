"""matriz de retorno de material por cidade, atividade e focus

Preenche os quatro parâmetros de retorno que estavam `NULL` desde a fase 0 e
acrescenta as variantes de cidade com bônus. O retorno deixa de ser um valor
único e passa a ser resolvido por (atividade, cidade, focus).

O que mudou em relação à regra "sem valor confirmado, fica UNKNOWN": estes
números **têm** procedência, e ela vai gravada por extenso em `source`. Não são
medição no jogo — continuam abertos em `docs/04-taxas.md` — mas deixaram de ser
"sem fonte" e viraram estimativa de alta fidelidade. A diferença prática é que
o cálculo roda e a interface informa de onde veio o número, em vez de responder
UNKNOWN para tudo.

Revision ID: 0006_matriz_retorno
Revises: 0005_rotas_transporte
Create Date: 2026-09-16
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0006_matriz_retorno'
down_revision: str | None = '0005_rotas_transporte'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Procedência exata, gravada em toda linha da matriz. `docs/04-taxas.md` exige
# dizer de qual página e de que data -- e, aqui, também o que NÃO foi feito.
FONTE = (
    "engenharia reversa da comunidade (logs de transacao + simulacao de alta "
    "amostragem); albioncodex, albionfreemarket, albiononlinegrind; consultado em "
    "16/09/2026; nao auditado contra codigo da Sandbox"
)

# Atividade x local x focus. Refino e craft têm bônus de cidade diferentes: o de
# refino segue o recurso, o de craft segue a família do item.
MATRIZ = [
    ("refining.return_rate.bonus.base", 0.367,
     "Retorno de refino na cidade com bonus do recurso, sem Focus."),
    ("refining.return_rate.bonus.focus", 0.539,
     "Retorno de refino na cidade com bonus do recurso, com Focus."),
    ("refining.return_rate.base", 0.152,
     "Retorno de refino fora da cidade com bonus, sem Focus."),
    ("refining.return_rate.focus", 0.435,
     "Retorno de refino fora da cidade com bonus, com Focus."),
    ("crafting.return_rate.bonus.base", 0.248,
     "Retorno de craft na cidade com bonus da familia do item, sem Focus."),
    ("crafting.return_rate.bonus.focus", 0.477,
     "Retorno de craft na cidade com bonus da familia do item, com Focus."),
    ("crafting.return_rate.base", 0.152,
     "Retorno de craft fora da cidade com bonus, sem Focus."),
    ("crafting.return_rate.focus", 0.435,
     "Retorno de craft fora da cidade com bonus, com Focus."),
]

# Família de item -> prefixos reais de `unique_name`, conferidos contra o
# catálogo importado (`base_name` sem o `T{n}_`). Prefixo e não substring de
# propósito: `2H_BOW` pega `2H_BOW_AVALON` e **não** pega `2H_CROSSBOW`, que é
# de outra cidade.
#
# O que não deu para mapear com confiança ficou de fora e está listado em
# `crafting.city_bonus_unmapped`. Item que não casa com nenhum prefixo cai no
# retorno sem bônus, que é o lado conservador de errar.
FAMILIAS_POR_CIDADE = {
    "martlock": [
        "MAIN_AXE", "2H_AXE",
        "SHOES_PLATE",
        "MAIN_FROSTSTAFF", "2H_FROSTSTAFF", "2H_GLACIALSTAFF",
        "OFF_",
    ],
    "fort-sterling": [
        "MAIN_HAMMER", "2H_HAMMER", "2H_POLEHAMMER",
        "MAIN_SPEAR", "2H_SPEAR",
        "HEAD_PLATE",
        "MAIN_HOLYSTAFF", "2H_HOLYSTAFF", "2H_DIVINESTAFF",
        "ARMOR_CLOTH",
    ],
    "lymhurst": [
        "MAIN_SWORD", "2H_CLAYMORE", "2H_DUALSWORD",
        "2H_BOW", "2H_LONGBOW", "2H_WARBOW",
        "HEAD_LEATHER", "SHOES_LEATHER",
        "MAIN_ARCANESTAFF", "2H_ARCANESTAFF", "2H_ENIGMATICSTAFF",
    ],
    "bridgewatch": [
        "ARMOR_PLATE",
        "MAIN_DAGGER", "2H_DAGGERPAIR",
        "MAIN_1HCROSSBOW", "2H_CROSSBOW", "2H_CROSSBOWLARGE",
        "MAIN_CURSEDSTAFF", "2H_CURSEDSTAFF", "2H_DEMONICSTAFF",
        "SHOES_CLOTH",
    ],
    "thetford": [
        "MAIN_MACE", "2H_MACE",
        "ARMOR_LEATHER",
        "MAIN_FIRESTAFF", "2H_FIRESTAFF", "2H_INFERNOSTAFF",
        "MAIN_NATURESTAFF", "2H_NATURESTAFF", "2H_WILDSTAFF",
        "HEAD_CLOTH",
    ],
    "caerleon": [
        "CAPEITEM_FW_",
        "BAG",
        "2H_TOOL_",
        "ARMOR_GATHERER", "HEAD_GATHERER", "SHOES_GATHERER",
        "MEAL_",
        "POTION_",
    ],
}

# O que o briefing listou e não foi possível casar com um prefixo do dump sem
# aproximar. Fica gravado para a tela poder dizer "não sei" em vez de calcular
# com bônus errado.
NAO_MAPEADO = {
    "martlock": [
        "cajados de quartzo: nao existe 'quartz staff' no dump. O candidato e "
        "2H_QUARTERSTAFF (bastao), mas a traducao nao confirma -- UNKNOWN."
    ],
    "geral": [
        "Linhas de arma sem confirmacao de familia ficaram de fora: HALBERD e "
        "SCYTHE (machados), GLAIVE (lancas), CLAWPAIR (adagas), FLAIL (macas), "
        "KNUCKLES, SHAPESHIFTER, DOUBLEBLADEDSTAFF, IRONCLADEDSTAFF, QUARTERSTAFF. "
        "Sem bonus, elas caem no retorno base -- errar para menos e o lado seguro."
    ],
}

JSON_PARAMS = [
    (
        "crafting.city_bonus_families",
        json.dumps(FAMILIAS_POR_CIDADE),
        "Prefixos de unique_name com bonus de craft, por cidade.",
        "briefing do dono do projeto em 16/09/2026; prefixos conferidos contra o "
        "catalogo importado do ao-bin-dumps",
    ),
    (
        "crafting.city_bonus_unmapped",
        json.dumps(NAO_MAPEADO),
        "Familias citadas no briefing que nao foi possivel mapear com confianca.",
        "decisao do projeto: nao aproximar mapeamento de familia",
    ),
    (
        # O bônus de refino segue o RECURSO, e esse mapeamento não foi fornecido.
        # Sem ele, /refining não tem como dizer qual cidade rende 0,367.
        "refining.city_bonus_resources",
        "null",
        "Recurso com bonus de refino, por cidade. UNKNOWN: mapeamento nao levantado.",
        "UNKNOWN",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    atualiza = sa.text(
        "INSERT INTO config_parameters (key, value, scope, description, source) "
        "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
        "ON CONFLICT (key) DO UPDATE SET "
        "value = EXCLUDED.value, description = EXCLUDED.description, "
        "source = EXCLUDED.source"
    )

    conn.execute(
        atualiza,
        [
            {"key": key, "value": json.dumps(valor), "description": descricao, "source": FONTE}
            for key, valor, descricao in MATRIZ
        ],
    )
    conn.execute(
        atualiza,
        [
            {"key": key, "value": valor, "description": descricao, "source": fonte}
            for key, valor, descricao, fonte in JSON_PARAMS
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Volta ao estado anterior: as quatro chaves originais existiam e eram NULL.
    conn.execute(
        sa.text(
            "UPDATE config_parameters SET value = 'null'::jsonb, source = 'UNKNOWN' "
            "WHERE key = ANY(:keys)"
        ),
        {
            "keys": [
                "crafting.return_rate.base",
                "crafting.return_rate.focus",
                "refining.return_rate.base",
                "refining.return_rate.focus",
            ]
        },
    )
    # As chaves novas somem de vez.
    conn.execute(
        sa.text("DELETE FROM config_parameters WHERE key = ANY(:keys)"),
        {
            "keys": [
                "refining.return_rate.bonus.base",
                "refining.return_rate.bonus.focus",
                "crafting.return_rate.bonus.base",
                "crafting.return_rate.bonus.focus",
                *[key for key, *_ in JSON_PARAMS],
            ]
        },
    )
