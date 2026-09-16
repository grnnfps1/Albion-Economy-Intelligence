"""rotas de transporte e risco de zona

Cria `transport_routes`, semeia a zona de cada par origem-destino e acrescenta
as duas probabilidades de perda a `config_parameters`, ambas em zero.

Revision ID: 0005_rotas_transporte
Revises: 0004_agricultura
Create Date: 2026-09-16 14:15:52.074537
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0005_rotas_transporte'
down_revision: str | None = '0004_agricultura'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Locais em zona aberta. Qualquer rota com uma ponta aqui atravessa vermelha ou
# preta -- a classificação é pelas pontas, porque o caminho é escolha do jogador
# e o que temos no dado são os dois mercados.
ZONA_ABERTA = ("caerleon", "black-market")


def _zona(origem: str, destino: str) -> str:
    if origem in ZONA_ABERTA or destino in ZONA_ABERTA:
        return "VERMELHA_PRETA"
    return "AZUL"


def _semear_rotas() -> None:
    """Uma linha por par ordenado de locais ativos.

    Linhas com `is_manual` ficam intactas: a regra genérica erra em Brecilien,
    que é `royal_city` no cadastro mas só se alcança por portal das Brumas, e
    quem corrigir à mão não pode ser sobrescrito por um re-seed.
    """
    conn = op.get_bind()
    locais = conn.execute(sa.text("SELECT id, slug FROM locations WHERE active IS TRUE")).all()

    linhas = [
        {"origem": o_id, "destino": d_id, "zona": _zona(o_slug, d_slug)}
        for o_id, o_slug in locais
        for d_id, d_slug in locais
        if o_id != d_id
    ]
    if not linhas:
        return

    conn.execute(
        sa.text(
            "INSERT INTO transport_routes "
            "(origin_location_id, destination_location_id, zone, is_manual) "
            "VALUES (:origem, :destino, :zona, FALSE) "
            "ON CONFLICT (origin_location_id, destination_location_id) DO NOTHING"
        ),
        linhas,
    )


# Probabilidade de perder a carga, por zona. Padrão **zero** de propósito, e a
# diferença em relação às taxas é deliberada: taxa ausente vira UNKNOWN porque
# calcular sem imposto inventa lucro; risco ausente vira zero porque significa
# "não estou modelando perda", e o ajustado sai idêntico ao bruto, visivelmente.
RISCO = [
    (
        "risk.loss_probability.blue",
        "Probabilidade de perder a carga numa rota entre cidades reais. "
        "Preferencia do usuario; padrao 0 = risco nao modelado.",
    ),
    (
        "risk.loss_probability.red_black",
        "Probabilidade de perder a carga numa rota que passa por Caerleon ou "
        "pelo Black Market. Preferencia do usuario; padrao 0 = risco nao modelado.",
    ),
]


def _semear_risco() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO config_parameters (key, value, scope, description, source) "
            "VALUES (:key, CAST(:value AS jsonb), 'global', :description, :source) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        [
            {
                "key": key,
                "value": "0",
                "description": descricao,
                "source": "decisao do projeto: padrao zero, e preferencia do usuario",
            }
            for key, descricao in RISCO
        ],
    )


def upgrade() -> None:
    op.create_table('transport_routes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('origin_location_id', sa.SmallInteger(), nullable=False),
    sa.Column('destination_location_id', sa.SmallInteger(), nullable=False),
    sa.Column('zone', sa.String(length=16), nullable=False),
    sa.Column('distance_label', sa.String(length=32), nullable=True),
    sa.Column('base_cost_per_weight', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('estimated_minutes', sa.SmallInteger(), nullable=True),
    sa.Column('is_manual', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("zone IN ('MESMA_CIDADE', 'AZUL', 'VERMELHA_PRETA')", name='ck_transport_routes_zone'),
    sa.CheckConstraint('origin_location_id <> destination_location_id', name='ck_transport_routes_distintos'),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['origin_location_id'], ['locations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_transport_routes_par', 'transport_routes', ['origin_location_id', 'destination_location_id'], unique=True)
    _semear_rotas()
    _semear_risco()


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM config_parameters WHERE key = ANY(:keys)"),
        {"keys": [key for key, _ in RISCO]},
    )
    op.drop_index('uq_transport_routes_par', table_name='transport_routes')
    op.drop_table('transport_routes')
