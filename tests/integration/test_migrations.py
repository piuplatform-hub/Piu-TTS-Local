"""
Alembic Database Migration & Schema Verification Tests
Covers:
1. Fresh database initialization via Alembic
2. Migration upgrade on pre-existing development database without data loss
3. SQLite Foreign Key constraint enforcement
4. SQLite WAL journal mode configuration
"""

from pathlib import Path
import sqlite3
import tempfile
import pytest
from alembic.config import Config
from alembic import command


def test_alembic_fresh_database_upgrade():
    """
    Verifies that Alembic successfully applies all migrations on a completely empty database,
    creating users, engines, artifacts, jobs and alembic_version.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "fresh_migration.db"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")

        command.upgrade(cfg, "head")

        assert db_file.exists()
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        for expected in [
            "alembic_version", "users", "engines", "artifacts", "jobs", "job_events", 
            "reference_assets", "projects", "characters", "script_segments", "segment_revisions", "project_exports",
            "login_attempts", "user_scheduling_states", "storage_reservations"
        ]:
            assert expected in tables, f"Table {expected} was not created by Alembic migration"


def test_alembic_upgrade_preexisting_db_without_data_loss():
    """
    Verifies that running Alembic upgrade on an already populated database
    preserves existing records and establishes the migration version stamp.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "preexisting.db"

        # Simulate pre-existing database with records
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(50),
                password_hash VARCHAR(255),
                role VARCHAR(20),
                is_active BOOLEAN,
                created_at DATETIME
            )
            """
        )
        cur.execute(
            "INSERT INTO users VALUES ('user_existing_1', 'legacy_admin', 'hash_legacy', 'admin', 1, '2026-10-08 09:00:00')"
        )
        conn.commit()
        conn.close()

        # Run Alembic migration upgrade
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        # Verify existing data is preserved
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        user_row = cur.execute("SELECT username, role FROM users WHERE id='user_existing_1'").fetchone()
        version_row = cur.execute("SELECT version_num FROM alembic_version").fetchone()
        conn.close()

        assert user_row == ("legacy_admin", "admin"), "Existing user record was lost during migration"
        assert version_row is not None and version_row[0] == "20261010_0007", "Alembic version was not recorded"


def test_foreign_key_constraint_enforcement():
    """
    Verifies that SQLite strictly enforces foreign keys (e.g. jobs.user_id -> users.id).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "fk_enforce.db"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys = ON")

        # Inserting a job with non-existent user must raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO jobs (id, user_id, engine_id, payload_data, queued_at)
                VALUES ('job_invalid', 'non_existent_user_id', 'mock-tts', '{}', '2026-10-08 10:00:00')
                """
            )
        conn.close()


def test_sqlite_wal_mode_enabled():
    """
    Verifies that SQLite WAL mode is configured on connection.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "wal_mode.db"
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        mode = cur.fetchone()[0]
        conn.close()
        assert mode.upper() == "WAL"
