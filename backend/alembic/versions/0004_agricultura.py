"""agricultura e animais

Cria `farmables` e `farmable_outputs` e acrescenta nutrição ao catálogo.

Revision ID: 0004_agricultura
Revises: 0003_receitas
Create Date: 2026-09-16 13:38:03.212632
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0004_agricultura'
down_revision: str | None = '0003_receitas'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('farmables',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('station', sa.String(length=32), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('cycle_seconds', sa.Integer(), nullable=True),
    sa.Column('grow_seconds', sa.Integer(), nullable=True),
    sa.Column('product_seconds', sa.Integer(), nullable=True),
    sa.Column('focus_cost', sa.Integer(), nullable=True),
    sa.Column('max_cycles', sa.SmallInteger(), nullable=True),
    sa.Column('active_farm_bonus', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('npc_silver_cost', sa.Integer(), nullable=True),
    sa.Column('grown_item_id', sa.Integer(), nullable=True),
    sa.Column('accepted_food_category', sa.String(length=32), nullable=True),
    sa.Column('seconds_per_nutrition', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('nutrition_max', sa.Integer(), nullable=True),
    sa.Column('favorite_food_item_id', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('seed', 'baby', 'grown')", name='ck_farmables_role'),
    sa.CheckConstraint("station IN ('farm', 'herbgarden', 'pasture', 'kennel')", name='ck_farmables_station'),
    sa.CheckConstraint('cycle_seconds IS NULL OR cycle_seconds > 0', name='ck_farmables_cycle_seconds'),
    sa.ForeignKeyConstraint(['favorite_food_item_id'], ['items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['grown_item_id'], ['items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_farmables_item', 'farmables', ['item_id'], unique=True)
    op.create_index('ix_farmables_station', 'farmables', ['station'], unique=False)
    op.create_table('farmable_outputs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('farmable_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('amount_min', sa.Integer(), nullable=False),
    sa.Column('amount_max', sa.Integer(), nullable=False),
    sa.Column('chance', sa.Numeric(precision=6, scale=4), nullable=False),
    sa.CheckConstraint("role IN ('harvest', 'product', 'grown', 'seed_return', 'offspring')", name='ck_farmable_outputs_role'),
    sa.CheckConstraint('amount_min >= 0 AND amount_max >= amount_min', name='ck_farmable_outputs_amount'),
    sa.CheckConstraint('chance >= 0 AND chance <= 1', name='ck_farmable_outputs_chance'),
    sa.ForeignKeyConstraint(['farmable_id'], ['farmables.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_farmable_outputs', 'farmable_outputs', ['farmable_id', 'item_id', 'role'], unique=True)
    op.add_column('items', sa.Column('nutrition', sa.Integer(), nullable=True))
    op.add_column('items', sa.Column('food_category', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('items', 'food_category')
    op.drop_column('items', 'nutrition')
    op.drop_index('uq_farmable_outputs', table_name='farmable_outputs')
    op.drop_table('farmable_outputs')
    op.drop_index('ix_farmables_station', table_name='farmables')
    op.drop_index('ix_farmables_item', table_name='farmables')
    op.drop_table('farmables')
