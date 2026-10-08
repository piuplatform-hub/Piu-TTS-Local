"""Phase 5A RBAC, Quotas & Login Protection: login_attempts table, users.storage_quota_mb

Revision ID: 20261009_0005
Revises: 20261008_0004
Create Date: 2026-10-09 00:52:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261009_0005'
down_revision: Union[str, None] = '20261008_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. login_attempts table
    if 'login_attempts' not in tables:
        op.create_table(
            'login_attempts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('ip_address', sa.String(length=45), nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('attempted_at', sa.DateTime(), nullable=False),
            sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_login_attempts_ip_address', 'login_attempts', ['ip_address'])
        op.create_index('ix_login_attempts_username', 'login_attempts', ['username'])
        op.create_index('ix_login_attempts_attempted_at', 'login_attempts', ['attempted_at'])

    # 2. users.storage_quota_mb column
    user_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'storage_quota_mb' not in user_columns:
        op.add_column('users', sa.Column('storage_quota_mb', sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'login_attempts' in tables:
        op.drop_index('ix_login_attempts_attempted_at', table_name='login_attempts')
        op.drop_index('ix_login_attempts_username', table_name='login_attempts')
        op.drop_index('ix_login_attempts_ip_address', table_name='login_attempts')
        op.drop_table('login_attempts')

    user_columns = [col['name'] for col in inspector.get_columns('users')]
    if 'storage_quota_mb' in user_columns:
        # SQLite drop_column requires batch mode
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('storage_quota_mb')
