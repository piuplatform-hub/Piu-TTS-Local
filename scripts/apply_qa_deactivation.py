#!/usr/bin/env python3
"""
AI Voice Studio — Phase 5B Gate A: Controlled Transactional QA Deactivation Wrapper
Enforces foreign-key validation, verifies exact row count (13 accounts),
and ensures zero foreign-key violations before committing.
DO NOT EXECUTE ON PRODUCTION UNTIL PRODUCT OWNER GATE A APPROVAL.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

TARGET_QA_ACCOUNTS = [
    "victim_account",
    "alice_shared",
    "bob_shared",
    "concurrent_user",
    "reset_user",
    "spoof_user",
    "real_existing_user",
    "healthy_user",
    "crashed_worker_user",
    "stale_user",
    "compete_user",
    "large_output_user",
    "export_fail_user",
]


def apply_deactivation(db_path: Path, execute: bool = False) -> dict:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.isolation_level = None  # Autocommit mode so we control BEGIN/COMMIT manually
    cur = conn.cursor()

    try:
        # 1. Enable foreign keys OUTSIDE of any transaction
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("PRAGMA foreign_keys;")
        fk_status = cur.fetchone()
        if not fk_status or fk_status[0] != 1:
            raise RuntimeError("Failed to enable SQLite foreign_keys constraint enforcement.")

        # 2. Pre-flight check: Verify existing user inventory
        cur.execute("SELECT username, is_active FROM users;")
        all_users = dict(cur.fetchall())

        if "acceptance_qa" not in all_users:
            raise RuntimeError("Admin account 'acceptance_qa' was not found in users table!")

        found_qa = [u for u in TARGET_QA_ACCOUNTS if u in all_users]
        if len(found_qa) != len(TARGET_QA_ACCOUNTS):
            missing = set(TARGET_QA_ACCOUNTS) - set(found_qa)
            raise RuntimeError(f"Expected 13 QA accounts, but found {len(found_qa)}. Missing: {missing}")

        # 3. Begin explicit transaction
        cur.execute("BEGIN TRANSACTION;")

        placeholders = ",".join("?" for _ in TARGET_QA_ACCOUNTS)
        cur.execute(
            f"UPDATE users SET is_active = 0 WHERE username IN ({placeholders});",
            TARGET_QA_ACCOUNTS,
        )
        updated_count = cur.rowcount
        if updated_count != len(TARGET_QA_ACCOUNTS):
            raise RuntimeError(
                f"Rowcount mismatch: expected {len(TARGET_QA_ACCOUNTS)} rows updated, got {updated_count}."
            )

        # 4. Enforce PRAGMA foreign_key_check inside transaction
        cur.execute("PRAGMA foreign_key_check;")
        fk_violations = cur.fetchall()
        if fk_violations:
            raise RuntimeError(f"Foreign key violations detected ({len(fk_violations)} violations): {fk_violations}")

        # 5. Verify admin account is untouched
        cur.execute("SELECT is_active FROM users WHERE username = 'acceptance_qa';")
        admin_active = cur.fetchone()
        if not admin_active or admin_active[0] != 1:
            raise RuntimeError("CRITICAL: Admin account 'acceptance_qa' was inadvertently modified!")

        # 6. Commit or Rollback based on execution flag
        if execute:
            cur.execute("COMMIT;")
            action_result = "COMMITTED"
        else:
            cur.execute("ROLLBACK;")
            action_result = "ROLLED_BACK (DRY-RUN)"

        return {
            "status": "SUCCESS",
            "action": action_result,
            "target_accounts_count": len(TARGET_QA_ACCOUNTS),
            "updated_count": updated_count,
            "fk_violations": 0,
            "admin_preserved": True,
        }

    except Exception as e:
        try:
            cur.execute("ROLLBACK;")
        except Exception:
            pass
        raise e
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="AI Voice Studio — Transactional QA Account Deactivation")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Commit changes to database. Defaults to dry-run (automatic rollback) if omitted.",
    )
    args = parser.parse_args()

    db_file = Path(args.db_path)
    print("=" * 70)
    print("AI VOICE STUDIO — CONTROLLED QA ACCOUNT DEACTIVATION")
    print("=" * 70)
    print(f"Target Database : {db_file}")
    print(f"Execution Mode  : {'LIVE EXECUTE' if args.execute else 'DRY RUN (ROLLBACK)'}")
    print(f"Target Accounts : {len(TARGET_QA_ACCOUNTS)} QA accounts")
    print("-" * 70)

    try:
        res = apply_deactivation(db_file, execute=args.execute)
        print(f"[+] Status              : {res['status']}")
        print(f"[+] Action              : {res['action']}")
        print(f"[+] QA Accounts Updated : {res['updated_count']} / {res['target_accounts_count']}")
        print(f"[+] Foreign Key Check   : 0 violations (Passed)")
        print(f"[+] Admin Preserved     : {res['admin_preserved']}")
        print("=" * 70)
    except Exception as e:
        print(f"[!] FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
