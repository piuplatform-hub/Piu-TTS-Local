"""Reference Audio Assets Schema

Revision ID: 20261008_0003
Revises: 20261008_0002
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261008_0003'
down_revision: Union[str, None] = '20261008_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'reference_assets' not in tables:
        op.create_table(
            'reference_assets',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('file_hash_sha256', sa.String(length=64), nullable=False),
            sa.Column('file_size_bytes', sa.Integer(), nullable=False),
            sa.Column('duration_seconds', sa.Float(), nullable=False),
            sa.Column('sample_rate', sa.Integer(), nullable=False),
            sa.Column('channels', sa.Integer(), nullable=False),
            sa.Column('format', sa.String(length=10), nullable=False),
            sa.Column('voice_use_consent', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_reference_assets_user_id'), 'reference_assets', ['user_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'reference_assets' in tables:
        op.drop_index(op.f('ix_reference_assets_user_id'), table_name='reference_assets')
        op.drop_table('reference_assets')
