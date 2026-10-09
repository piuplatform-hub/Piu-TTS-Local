"""
Safe Data Cleanup Script for AI Voice Studio
Removes manual TCP test artifacts from D:/AIVoiceStudioData/studio.db
Ensures a backup is created before executing any changes.
"""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
import sys

MAIN_DB_PATH = Path("D:/AIVoiceStudioData/studio.db")
BACKUP_DIR = Path("D:/AIVoiceStudioData/backups")


def cleanup_manual_test_data():
    if not MAIN_DB_PATH.exists():
        print(f"[SKIP] Database {MAIN_DB_PATH} does not exist.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"studio_db_pre_cleanup_{ts}.db"

    # Step 1: Create physical backup
    shutil.copy2(MAIN_DB_PATH, backup_file)
    print(f"[BACKUP] Safety copy created at: {backup_file}")

    conn = sqlite3.connect(MAIN_DB_PATH)
    cur = conn.cursor()

    try:
        # Step 2: Audit specific target test records before deletion
        cur.execute("SELECT id, username, role FROM users WHERE id = 'test_tcp_user' AND username = 'tcp_victim'")
        target_users = cur.fetchall()

        cur.execute("SELECT id, ip_address, username, attempted_at FROM login_attempts WHERE username = 'tcp_victim' OR ip_address = '203.0.113.199'")
        target_attempts = cur.fetchall()

        print(f"[AUDIT] Found {len(target_users)} user(s) to remove: {target_users}")
        print(f"[AUDIT] Found {len(target_attempts)} login attempt(s) to remove:")
        for att in target_attempts:
            print(f"   - ID: {att[0]}, IP: {att[1]}, User: {att[2]}, At: {att[3]}")

        if not target_users and not target_attempts:
            print("[INFO] No manual test artifacts found. Database is already clean.")
            conn.close()
            return

        # Step 3: Perform atomic deletion
        cur.execute("DELETE FROM login_attempts WHERE username = 'tcp_victim' OR ip_address = '203.0.113.199'")
        deleted_attempts = cur.rowcount

        cur.execute("DELETE FROM users WHERE id = 'test_tcp_user' AND username = 'tcp_victim'")
        deleted_users = cur.rowcount

        conn.commit()
        print(f"[SUCCESS] Deleted {deleted_users} test user(s) and {deleted_attempts} test login attempt(s).")

        # Step 4: Verification - Ensure real users are preserved
        cur.execute("SELECT id, username, role FROM users")
        remaining_users = cur.fetchall()
        print(f"[VERIFY] Remaining users in studio.db ({len(remaining_users)}):")
        for u in remaining_users:
            print(f"   - {u[1]} ({u[2]}, ID: {u[0]})")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Transaction failed, rolled back: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    cleanup_manual_test_data()
