"""Phase 4 Professional Studio Schema: projects, characters, script_segments, segment_revisions, project_exports

Revision ID: 20261008_0004
Revises: 20261008_0003
Create Date: 2026-10-08 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261008_0004'
down_revision: Union[str, None] = '20261008_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. projects table
    if 'projects' not in tables:
        op.create_table(
            'projects',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('project_type', sa.String(length=50), nullable=False, server_default='narration'),
            sa.Column('settings_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)

    # 2. characters table
    if 'characters' not in tables:
        op.create_table(
            'characters',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('avatar_color', sa.String(length=20), nullable=False, server_default='#10b981'),
            sa.Column('engine_id', sa.String(length=50), nullable=False),
            sa.Column('voice_id', sa.String(length=100), nullable=False),
            sa.Column('language', sa.String(length=10), nullable=False, server_default='vi'),
            sa.Column('parameters_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['engine_id'], ['engines.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_characters_project_id'), 'characters', ['project_id'], unique=False)

    # 3. script_segments table
    if 'script_segments' not in tables:
        op.create_table(
            'script_segments',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('character_id', sa.String(length=36), nullable=True),
            sa.Column('sequence_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('language', sa.String(length=10), nullable=False, server_default='vi'),
            sa.Column('engine_id', sa.String(length=50), nullable=False),
            sa.Column('voice_id', sa.String(length=100), nullable=False),
            sa.Column('parameters_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('pause_after_ms', sa.Integer(), nullable=False, server_default='300'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('active_artifact_id', sa.String(length=36), nullable=True),
            sa.Column('last_job_id', sa.String(length=36), nullable=True),
            sa.Column('text_hash', sa.String(length=64), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['engine_id'], ['engines.id']),
            sa.ForeignKeyConstraint(['active_artifact_id'], ['artifacts.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['last_job_id'], ['jobs.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_script_segments_project_id'), 'script_segments', ['project_id'], unique=False)
        op.create_index(op.f('ix_script_segments_character_id'), 'script_segments', ['character_id'], unique=False)
        op.create_index(op.f('ix_script_segments_sequence_order'), 'script_segments', ['sequence_order'], unique=False)
        op.create_index(op.f('ix_script_segments_status'), 'script_segments', ['status'], unique=False)

    # 4. segment_revisions table
    if 'segment_revisions' not in tables:
        op.create_table(
            'segment_revisions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('segment_id', sa.String(length=36), nullable=False),
            sa.Column('revision_number', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('engine_id', sa.String(length=50), nullable=False),
            sa.Column('voice_id', sa.String(length=100), nullable=False),
            sa.Column('parameters_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('artifact_id', sa.String(length=36), nullable=False),
            sa.Column('job_id', sa.String(length=36), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['segment_id'], ['script_segments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_segment_revisions_segment_id'), 'segment_revisions', ['segment_id'], unique=False)

    # 5. project_exports table
    if 'project_exports' not in tables:
        op.create_table(
            'project_exports',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('format', sa.String(length=10), nullable=False),
            sa.Column('sample_rate', sa.Integer(), nullable=False, server_default='48000'),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('duration_seconds', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
            sa.Column('loudness_lufs', sa.Float(), nullable=True),
            sa.Column('segment_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_project_exports_project_id'), 'project_exports', ['project_id'], unique=False)
        op.create_index(op.f('ix_project_exports_user_id'), 'project_exports', ['user_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    for tbl in ['project_exports', 'segment_revisions', 'script_segments', 'characters', 'projects']:
        if tbl in tables:
            op.drop_table(tbl)
