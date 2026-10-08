"""Durable Jobs Queue and Events Schema

Revision ID: 20261008_0002
Revises: 20261008_0001
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261008_0002'
down_revision: Union[str, None] = '20261008_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Alter Jobs table using SQLite batch mode
    if 'jobs' in tables:
        job_cols = [c['name'] for c in inspector.get_columns('jobs')]
        with op.batch_alter_table('jobs') as batch_op:
            if 'priority' not in job_cols:
                batch_op.add_column(sa.Column('priority', sa.Integer(), server_default='0', nullable=False))
            if 'resource_type' not in job_cols:
                batch_op.add_column(sa.Column('resource_type', sa.String(length=10), server_default='cpu', nullable=False))
            if 'attempt_count' not in job_cols:
                batch_op.add_column(sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False))
            if 'max_retries' not in job_cols:
                batch_op.add_column(sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False))
            if 'current_attempt_id' not in job_cols:
                batch_op.add_column(sa.Column('current_attempt_id', sa.String(length=36), nullable=True))
            if 'locked_by' not in job_cols:
                batch_op.add_column(sa.Column('locked_by', sa.String(length=100), nullable=True))
            if 'scheduled_at' not in job_cols:
                batch_op.add_column(sa.Column('scheduled_at', sa.DateTime(), nullable=True))
            if 'waiting_reason' not in job_cols:
                batch_op.add_column(sa.Column('waiting_reason', sa.String(length=255), nullable=True))

            existing_indexes = [idx['name'] for idx in inspector.get_indexes('jobs')]
            if 'ix_jobs_queue_order' not in existing_indexes:
                batch_op.create_index('ix_jobs_queue_order', ['status', 'priority', 'queued_at'], unique=False)

    # 2. Create job_events table
    if 'job_events' not in tables:
        op.create_table(
            'job_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('job_id', sa.String(length=36), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_job_events_job_id', 'job_events', ['job_id'], unique=False)
        op.create_index('ix_job_events_job_id_id', 'job_events', ['job_id', 'id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'job_events' in tables:
        op.drop_index('ix_job_events_job_id_id', table_name='job_events')
        op.drop_index('ix_job_events_job_id', table_name='job_events')
        op.drop_table('job_events')

    if 'jobs' in tables:
        with op.batch_alter_table('jobs') as batch_op:
            batch_op.drop_index('ix_jobs_queue_order')
            batch_op.drop_column('waiting_reason')
            batch_op.drop_column('scheduled_at')
            batch_op.drop_column('locked_by')
            batch_op.drop_column('current_attempt_id')
            batch_op.drop_column('max_retries')
            batch_op.drop_column('attempt_count')
            batch_op.drop_column('resource_type')
            batch_op.drop_column('priority')
