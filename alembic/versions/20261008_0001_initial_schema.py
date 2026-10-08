"""Initial Schema: users, engines, artifacts, jobs

Revision ID: 20261008_0001
Revises: 
Create Date: 2026-10-08 10:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261008_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Users Table
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), server_default='editor', nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # 2. Engines Table
    if 'engines' not in tables:
        op.create_table(
            'engines',
            sa.Column('id', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('version', sa.String(length=20), nullable=False),
            sa.Column('approval_status', sa.String(length=20), server_default='approved', nullable=False),
            sa.Column('device_target', sa.String(length=20), server_default='cpu', nullable=False),
            sa.Column('capabilities', sa.JSON(), nullable=False),
            sa.Column('manifest_data', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    # 3. Artifacts Table
    if 'artifacts' not in tables:
        op.create_table(
            'artifacts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('owner_id', sa.String(length=36), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('file_hash_sha256', sa.String(length=64), nullable=True),
            sa.Column('file_size_bytes', sa.Integer(), server_default='0', nullable=False),
            sa.Column('duration_seconds', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('sample_rate', sa.Integer(), server_default='44100', nullable=False),
            sa.Column('format', sa.String(length=10), server_default='wav', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_artifacts_owner_id', 'artifacts', ['owner_id'], unique=False)

    # 4. Jobs Table
    if 'jobs' not in tables:
        op.create_table(
            'jobs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('engine_id', sa.String(length=50), nullable=False),
            sa.Column('idempotency_key', sa.String(length=100), nullable=True),
            sa.Column('job_type', sa.String(length=20), server_default='tts', nullable=False),
            sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
            sa.Column('progress_percent', sa.Integer(), server_default='0', nullable=False),
            sa.Column('worker_id', sa.String(length=50), nullable=True),
            sa.Column('lease_expires_at', sa.DateTime(), nullable=True),
            sa.Column('heartbeat_at', sa.DateTime(), nullable=True),
            sa.Column('payload_data', sa.JSON(), nullable=False),
            sa.Column('error_details', sa.JSON(), nullable=True),
            sa.Column('artifact_id', sa.String(length=36), nullable=True),
            sa.Column('queued_at', sa.DateTime(), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_user_idempotency_key'),
        )
        op.create_index('ix_jobs_engine_id', 'jobs', ['engine_id'], unique=False)
        op.create_index('ix_jobs_status', 'jobs', ['status'], unique=False)
        op.create_index('ix_jobs_user_id', 'jobs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_user_id', table_name='jobs')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index('ix_jobs_engine_id', table_name='jobs')
    op.drop_table('jobs')
    op.drop_index('ix_artifacts_owner_id', table_name='artifacts')
    op.drop_table('artifacts')
    op.drop_table('engines')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
