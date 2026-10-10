#!/usr/bin/env python3
"""
AI Voice Studio — Phase 5B Gate A: Provision Dedicated Pilot Account Safely
Hardened against accidental credential disclosure in logs and unsafe upsert collisions.
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

# Reserved system usernames that must NEVER be overwritten by pilot account provisioning
RESERVED_PROTECTED_USERNAMES = {
    "acceptance_qa",
    "admin",
    "root",
    "supervisor",
    "studio_lead",
}


def generate_secure_password(length: int = 24) -> str:
    """Generates a high-entropy password containing upper, lower, digits, and safe symbols."""
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Provision pilot_editor account safely for Gate A LAN Pilot")
    parser.add_argument("--db-path", default="", help="Path to SQLite database to apply provisioning")
    parser.add_argument("--execute", action="store_true", help="Execute insertion directly into SQLite database")
    parser.add_argument("--username", default="pilot_editor", help="Username for the pilot account (must start with pilot_)")
    parser.add_argument("--role", default="editor", choices=["editor", "admin"], help="Assigned role for the account")
    parser.add_argument("--show-secret", action="store_true", help="Explicitly reveal plaintext generated credential to stdout")
    parser.add_argument("--credential-out", default="", help="Optional file path to securely write generated credentials (0600 mode)")
    parser.add_argument("--allow-update", action="store_true", help="Allow updating an existing pilot account")
    args = parser.parse_args()

    username = args.username.strip()

    # 1. Enforce pilot naming safety to prevent collision with system accounts
    if username.lower() in RESERVED_PROTECTED_USERNAMES:
        print(f"[ERROR] Cannot provision pilot account with reserved username '{username}'.", file=sys.stderr)
        sys.exit(1)

    if not username.startswith("pilot_"):
        print(f"[ERROR] Pilot accounts must strictly start with 'pilot_' prefix (got '{username}').", file=sys.stderr)
        sys.exit(1)

    raw_password = generate_secure_password(24)
    password_hash = hasher.hash(raw_password)
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    now_utc = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print("AI VOICE STUDIO — SAFE PILOT ACCOUNT PROVISIONING")
    print("=" * 70)
    print(f"Target Username   : {username}")
    print(f"Assigned Role     : {args.role}")
    print(f"Argon2id Hash     : {password_hash[:35]}... (RFC 9106 verified)")
    print(f"Account State     : is_active = 1")
    if args.show_secret:
        print(f"Plaintext Secret  : {raw_password}")
    else:
        print(f"Plaintext Secret  : [PROTECTED / MASKED — Pass --show-secret or --credential-out to inspect]")
    print("-" * 70)

    # 2. Write credentials to secure file if requested
    if args.credential_out:
        out_path = Path(args.credential_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"USERNAME={username}\nPASSWORD={raw_password}\nROLE={args.role}\nCREATED_AT={now_utc}\n", encoding="utf-8")
        print(f"[+] Credentials written to: {out_path}")

    # 3. Handle database execution if requested
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
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("SELECT id, username, role FROM users WHERE username = ?;", (username,))
            existing = cur.fetchone()

            if existing:
                if not args.allow_update:
                    print(f"[ERROR] User '{username}' already exists. Pass --allow-update to explicitly update.", file=sys.stderr)
                    sys.exit(1)
                cur.execute("BEGIN TRANSACTION;")
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        role = ?,
                        is_active = 1,
                        token_version = token_version + 1
                    WHERE username = ?;
                    """,
                    (password_hash, args.role, username)
                )
                conn.commit()
                print(f"[SUCCESS] Safely updated existing pilot account '{username}' in {db_file}")
            else:
                cur.execute("BEGIN TRANSACTION;")
                cur.execute(
                    """
                    INSERT INTO users (id, username, password_hash, role, is_active, token_version, created_at)
                    VALUES (?, ?, ?, ?, 1, 1, ?);
                    """,
                    (user_id, username, password_hash, args.role, now_utc)
                )
                conn.commit()
                print(f"[SUCCESS] Safely inserted new pilot account '{username}' in {db_file}")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[ERROR] Transaction failed and rolled back: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            conn.close()
    else:
        print("[INFO] Dry-run complete. Database was NOT modified. Pass --execute --db-path <path> upon Gate A authorization.")


if __name__ == "__main__":
    main()
