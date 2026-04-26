"""add webhook secret

Revision ID: 1f3df93b0478
Revises: 0001_initial
Create Date: 2026-04-26 16:38:16.092512

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '1f3df93b0478'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column as nullable first to avoid "Cannot add a NOT NULL column with default value NULL"
    op.add_column('users', sa.Column('webhook_secret', sa.String(), nullable=True))
    
    # 2. Populate existing rows with a unique value (using 'id' as a proxy for the secret temporarily)
    op.execute("UPDATE users SET webhook_secret = id WHERE webhook_secret IS NULL")
    
    # 3. Use batch_op for SQLite compatibility to set NOT NULL and add constraints
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('webhook_secret', nullable=False)
        batch_op.create_unique_constraint('uq_users_webhook_secret', ['webhook_secret'])
        
        # Also handle the index to unique constraint conversion for username
        batch_op.drop_index(op.f('ix_users_username'))
        batch_op.create_unique_constraint('uq_users_username', ['username'])


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_webhook_secret', type_='unique')
        batch_op.drop_constraint('uq_users_username', type_='unique')
        batch_op.create_index(op.f('ix_users_username'), ['username'], unique=True)
        batch_op.drop_column('webhook_secret')
