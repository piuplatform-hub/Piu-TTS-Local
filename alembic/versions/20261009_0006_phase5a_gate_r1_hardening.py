"""Phase 5A Gate R1 Hardening: user_scheduling_states, storage_reservations, users.token_version

Revision ID: 20261009_0006
Revises: 20261009_0005
Create Date: 2026-10-09 08:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261009_0006'
down_revision: Union[str, None] = '20261009_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. user_scheduling_states table for persistent fair-share scheduling
    if 'user_scheduling_states' not in tables:
        op.create_table(
            'user_scheduling_states',
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('resource_type', sa.String(length=10), nullable=False),
            sa.Column('last_dispatched_at', sa.DateTime(), nullable=True),
            sa.Column('dispatched_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('user_id', 'resource_type'),
        )
        op.create_index('ix_user_scheduling_states_last_dispatched_at', 'user_scheduling_states', ['last_dispatched_at'])

    # 2. storage_reservations table for atomic capacity reservations
    if 'storage_reservations' not in tables:
        op.create_table(
            'storage_reservations',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=True),
            sa.Column('reservation_type', sa.String(length=30), nullable=False),
            sa.Column('reserved_bytes', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_storage_reservations_user_id', 'storage_reservations', ['user_id'])
        op.create_index('ix_storage_reservations_job_id', 'storage_reservations', ['job_id'])
        op.create_index('ix_storage_reservations_status', 'storage_reservations', ['status'])
        op.create_index('ix_storage_reservations_expires_at', 'storage_reservations', ['expires_at'])

    # 3. users.token_version column for session invalidation on password change
    user_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'token_version' not in user_columns:
        op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default=sa.text('1')))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'storage_reservations' in tables:
        op.drop_index('ix_storage_reservations_expires_at', table_name='storage_reservations')
        op.drop_index('ix_storage_reservations_status', table_name='storage_reservations')
        op.drop_index('ix_storage_reservations_job_id', table_name='storage_reservations')
        op.drop_index('ix_storage_reservations_user_id', table_name='storage_reservations')
        op.drop_table('storage_reservations')

    if 'user_scheduling_states' in tables:
        op.drop_index('ix_user_scheduling_states_last_dispatched_at', table_name='user_scheduling_states')
        op.drop_table('user_scheduling_states')

    user_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'token_version' in user_columns:
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('token_version')
