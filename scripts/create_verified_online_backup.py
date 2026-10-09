"""
Verified SQLite Online Backup Utility for AI Voice Studio
Uses the official SQLite Online Backup API (sqlite3.Connection.backup)
to produce a 100% consistent, self-contained snapshot under live WAL mode.
"""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

MAIN_DB_PATH = Path("D:/AIVoiceStudioData/studio.db")
BACKUP_DIR = Path("D:/AIVoiceStudioData/backups")


def create_verified_online_backup() -> Path:
    if not MAIN_DB_PATH.exists():
        print(f"[ERROR] Source database {MAIN_DB_PATH} does not exist.", file=sys.stderr)
        sys.exit(1)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"studio_db_online_backup_verified_{ts}.db"

    print(f"[ONLINE BACKUP] Starting SQLite Online Backup API from {MAIN_DB_PATH} -> {backup_file}...")

    src_conn = sqlite3.connect(str(MAIN_DB_PATH))
    dst_conn = sqlite3.connect(str(backup_file))

    try:
        # sqlite3.Connection.backup uses sqlite3_backup_* under the hood
        # with pages=0 to copy all pages atomically
        with dst_conn:
            src_conn.backup(dst_conn, pages=0)

        print("[ONLINE BACKUP] Pages copied successfully. Verifying integrity of backup...")

        # Integrity Check on newly created backup
        cur = dst_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        result = cur.fetchone()
        assert result and result[0] == "ok", f"Integrity check failed: {result}"

        # Quick stats audit
        cur.execute("SELECT COUNT(*) FROM users;")
        user_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM projects;")
        proj_count = cur.fetchone()[0]

        print(f"[ONLINE BACKUP] Verification PASS: integrity_check=ok, users={user_count}, projects={proj_count}")
        print(f"[ONLINE BACKUP] Verified backup created at: {backup_file}")
        return backup_file

    finally:
        dst_conn.close()
        src_conn.close()


if __name__ == "__main__":
    create_verified_online_backup()
