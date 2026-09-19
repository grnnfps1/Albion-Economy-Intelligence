"""taxas de mercado medidas no jogo

**Primeira vez que um parametro do projeto sai de "fonte de comunidade" para
"medicao direta".** Ate aqui todo numero gravado com valor vinha de engenharia
reversa da comunidade (fase 14), de anuncio oficial (fase 15) ou de conferencia
contra planilha de terceiro (fase 19). Estes foram lidos na tela do jogo.

    market.sell_order_setup_fee_pct  0.025   medicao no jogo
    market.buy_order_setup_fee_pct   0.025   medicao no jogo
    market.sales_tax_pct.premium     0.04    medicao no jogo
    market.sales_tax_pct.standard    0.08    confirmacao do usuario

As tres primeiras saem de Fort Sterling Market, 19/09/2026, conta com Premium.

**As procedencias sao diferentes, e a tabela guarda a diferenca.** O valor com
Premium foi medido com a notificacao do jogo discriminando preco, taxa e
recebido; o sem Premium veio de confirmacao do usuario. As duas sao melhores
que fonte de comunidade, e nenhuma e "derivada da outra" -- se o 8% fosse
obtido dobrando o 4%, seria chute com cara de medicao.

Revision ID: 0013_taxas_medidas
Revises: 0012_ilha
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0013_taxas_medidas'
down_revision: str | None = '0012_ilha'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `config_parameters.source` e varchar(255). A procedencia diz o que foi feito,
# onde e quando -- e o que a distingue das outras e a palavra "medicao".
FONTE_IMPOSTO = (
    "medicao direta no jogo, Fort Sterling Market, 19/09/2026, conta com "
    "Premium; notificacao de venda discriminando preco 140.440, taxa 5.618, "
    "recebido 134.822 = 4,0003% sobre o preco bruto"
)

FONTE_SETUP = (
    "medicao direta no jogo, Fort Sterling Market, 19/09/2026, conta com "
    "Premium; quatro ordens conferidas por saldo, cobrado na criacao nas duas "
    "pernas; uma das quatro nao fecha por arredondamento (docs/04-taxas.md)"
)

FONTE_STANDARD = (
    "confirmado pelo usuario, 19/09/2026; procedencia diferente da do imposto "
    "com Premium, que tem notificacao do jogo discriminando preco, taxa e "
    "recebido; nao derivado do valor com Premium"
)

MEDIDOS = [
    (
        "market.sell_order_setup_fee_pct",
        0.025,
        "Setup fee da ordem de venda. Cobrado na criacao, mesmo que a ordem "
        "nunca execute.",
        FONTE_SETUP,
    ),
    (
        "market.buy_order_setup_fee_pct",
        0.025,
        "Setup fee da ordem de compra. Medido igual ao da venda -- o motor ja "
        "usava uma taxa so para as duas pernas, e a medicao confirma.",
        FONTE_SETUP,
    ),
    (
        "market.sales_tax_pct.premium",
        0.04,
        "Imposto de venda com Premium. Incide sobre o preco **bruto**, nao "
        "sobre o liquido.",
        FONTE_IMPOSTO,
    ),
    (
        "market.sales_tax_pct.standard",
        0.08,
        "Imposto de venda sem Premium. Confirmado pelo usuario -- procedencia "
        "diferente da do valor com Premium, que tem notificacao do jogo. Nao "
        "foi derivado dobrando o outro.",
        FONTE_STANDARD,
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    for key, value, description, source in MEDIDOS:
        bind.execute(
            sa.text(
                "INSERT INTO config_parameters (key, value, scope, description, source) "
                "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
                "ON CONFLICT (key) DO UPDATE SET "
                "value = EXCLUDED.value, description = EXCLUDED.description, "
                "source = EXCLUDED.source"
            ),
            {"key": key, "value": str(value), "description": description, "source": source},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM config_parameters WHERE key = 'market.buy_order_setup_fee_pct'")
    )
    for key in (
        "market.sell_order_setup_fee_pct",
        "market.sales_tax_pct.premium",
        "market.sales_tax_pct.standard",
    ):
        bind.execute(
            sa.text(
                "UPDATE config_parameters SET value = 'null'::jsonb, source = 'UNKNOWN' "
                "WHERE key = :key"
            ),
            {"key": key},
        )
