"""Phase 6A: Reusable Voice Profiles Library

Revision ID: 20261010_0007
Revises: 20261009_0006
Create Date: 2026-10-10 15:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261010_0007'
down_revision: Union[str, None] = '20261009_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # Create voice_profiles table for reusable voice cloning profiles
    if 'voice_profiles' not in tables:
        op.create_table(
            'voice_profiles',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('engine_id', sa.String(length=50), nullable=False, server_default='vieneu-tts'),
            sa.Column('reference_asset_id', sa.String(length=36), sa.ForeignKey('reference_assets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('parameters_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_voice_profiles_user_id', 'voice_profiles', ['user_id'])
        op.create_index('ix_voice_profiles_reference_asset_id', 'voice_profiles', ['reference_asset_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'voice_profiles' in tables:
        op.drop_index('ix_voice_profiles_reference_asset_id', table_name='voice_profiles')
        op.drop_index('ix_voice_profiles_user_id', table_name='voice_profiles')
        op.drop_table('voice_profiles')
