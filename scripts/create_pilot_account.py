#!/usr/bin/env python3
"""
AI Voice Studio — Phase 5B Gate A: Provision Dedicated Pilot Editor Account
Generates a cryptographically strong, independent credential for 'pilot_editor'.
Outputs credential and transactional SQL. Does not mutate production unless --execute is passed.
"""

import argparse
import secrets
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from argon2 import PasswordHasher

hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def generate_secure_password(length: int = 20) -> str:
    """Generates a high-entropy password containing upper, lower, digits, and safe symbols."""
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Provision pilot_editor account for Gate A LAN Pilot")
    parser.add_argument("--db-path", default="", help="Path to SQLite database to apply provisioning")
    parser.add_argument("--execute", action="store_true", help="Execute insertion directly into SQLite database")
    parser.add_argument("--username", default="pilot_editor", help="Username for the pilot account")
    args = parser.parse_args()

    username = args.username.strip()
    raw_password = generate_secure_password(24)
    password_hash = hasher.hash(raw_password)
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    now_utc = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print("AI VOICE STUDIO — PILOT ACCOUNT PROVISIONING PREPARATION")
    print("=" * 70)
    print(f"Username          : {username}")
    print(f"Generated Password: {raw_password}")
    print(f"Argon2id Hash     : {password_hash[:40]}...")
    print(f"Assigned Role     : editor")
    print(f"Account State     : is_active = 1 (Active for Gate A Pilot)")
    print("-" * 70)

    sql_stmt = (
        f"BEGIN TRANSACTION;\n"
        f"INSERT INTO users (id, username, password_hash, role, is_active, token_version, created_at, updated_at)\n"
        f"VALUES ('{user_id}', '{username}', '{password_hash}', 'editor', 1, 1, '{now_utc}', '{now_utc}')\n"
        f"ON CONFLICT(username) DO UPDATE SET\n"
        f"    password_hash = '{password_hash}',\n"
        f"    is_active = 1,\n"
        f"    token_version = token_version + 1,\n"
        f"    updated_at = '{now_utc}';\n"
        f"COMMIT;\n"
    )

    print("Transactional SQL Statement:")
    print(sql_stmt)

    if args.execute:
        if not args.db_path:
            print("[ERROR] Cannot execute without --db-path specified.", file=sys.stderr)
            sys.exit(1)
        db_file = Path(args.db_path)
        if not db_file.is_file():
            print(f"[ERROR] Database file not found: {db_file}", file=sys.stderr)
            sys.exit(1)

        conn = sqlite3.connect(str(db_file))
        try:
            cur = conn.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active, token_version, created_at, updated_at)
                VALUES (?, ?, ?, 'editor', 1, 1, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    is_active = 1,
                    token_version = users.token_version + 1,
                    updated_at = excluded.updated_at;
                """,
                (user_id, username, password_hash, now_utc, now_utc)
            )
            conn.commit()
            print(f"[SUCCESS] Successfully provisioned/updated '{username}' in {db_file}")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Transaction failed and rolled back: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            conn.close()
    else:
        print("[INFO] Dry-run complete. Database was NOT modified. Pass --execute --db-path <path> upon Gate A authorization.")


if __name__ == "__main__":
    main()
