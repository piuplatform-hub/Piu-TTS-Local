"""
AI Voice Studio — SQLite Online Backup & Restore CLI
Usage:
    python -m apps.server.src.backup create [--dest <path>] [--no-verify]
    python -m apps.server.src.backup verify <path>
    python -m apps.server.src.backup restore <path> [--target <path>] [--no-safety]
    python -m apps.server.src.backup audit
"""

import argparse
import json
import sys
from pathlib import Path

from .services.backup_service import BackupService


def cmd_create(args):
    dest = args.dest if args.dest else None
    verify = not args.no_verify
    try:
        result = BackupService.create_online_backup(destination_path=dest, verify=verify)
        print("\n" + "=" * 60)
        print(" [AI VOICE STUDIO] ONLINE BACKUP CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f" Source:      {result['source_path']}")
        print(f" Destination: {result['backup_path']}")
        print(f" Size:        {result['file_size_bytes']:,} bytes")
        print(f" SHA256:      {result['sha256']}")
        if result.get("verification"):
            v = result["verification"]
            print(f" Integrity:   {v.get('integrity_check')} (Quick check: {v.get('quick_check')})")
            print(f" Alembic Rev: {v.get('alembic_version')}")
            print(f" Tables:      {json.dumps(v.get('tables', {}), indent=2)}")
        print("=" * 60 + "\n")
    except Exception as exc:
        print(f"ERROR: Backup creation failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_verify(args):
    path = Path(args.path)
    result = BackupService.verify_backup(path)
    print("\n" + "=" * 60)
    print(f" [AI VOICE STUDIO] BACKUP VERIFICATION REPORT")
    print("=" * 60)
    print(f" Path:        {result.get('path')}")
    print(f" Valid:       {result.get('is_valid')}")
    print(f" Size:        {result.get('file_size_bytes', 0):,} bytes")
    print(f" SHA256:      {result.get('sha256')}")
    print(f" Integrity:   {result.get('integrity_check')}")
    print(f" Quick check: {result.get('quick_check')}")
    print(f" Alembic Rev: {result.get('alembic_version')}")
    if result.get("tables"):
        print(" Tables & Row Counts:")
        for t, count in result["tables"].items():
            print(f"   - {t:20}: {count} rows")
    if result.get("error"):
        print(f" Error:       {result['error']}")
    print("=" * 60 + "\n")
    if not result.get("is_valid", False):
        sys.exit(1)


def cmd_restore(args):
    backup_path = Path(args.path)
    target = args.target if args.target else None
    safety = not args.no_safety
    try:
        result = BackupService.restore_backup(
            backup_path=backup_path,
            target_path=target,
            create_safety_backup=safety,
        )
        print("\n" + "=" * 60)
        print(" [AI VOICE STUDIO] DATABASE RESTORED SUCCESSFULLY")
        print("=" * 60)
        print(f" Restored from: {result['backup_restored']}")
        print(f" Target path:   {result['target_path']}")
        if result.get("safety_backup"):
            print(f" Safety backup: {result['safety_backup']}")
        v = result.get("verification", {})
        print(f" Target Status: Valid={v.get('is_valid')} | Integrity={v.get('integrity_check')}")
        print("=" * 60 + "\n")
    except Exception as exc:
        print(f"ERROR: Restore failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_audit(args):
    reports = BackupService.audit_existing_backups()
    print("\n" + "=" * 60)
    print(f" [AI VOICE STUDIO] AUDITING EXISTING DATABASE BACKUPS ({len(reports)} found)")
    print("=" * 60)
    for r in reports:
        print(f" File:        {r.get('file_name')} ({r.get('path')})")
        print(f" Valid:       {r.get('is_valid')}")
        print(f" Size:        {r.get('file_size_bytes', 0):,} bytes")
        print(f" SHA256:      {r.get('sha256')}")
        print(f" Integrity:   {r.get('integrity_check')}")
        print(f" Alembic Rev: {r.get('alembic_version')}")
        if r.get("tables"):
            print(f" Key Tables:  users={r['tables'].get('users', 0)}, jobs={r['tables'].get('jobs', 0)}, artifacts={r['tables'].get('artifacts', 0)}")
        print("-" * 60)
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AI Voice Studio Database Backup & Restore Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: create
    p_create = subparsers.add_parser("create", help="Create an online backup snapshot")
    p_create.add_argument("--dest", type=str, default=None, help="Destination file path")
    p_create.add_argument("--no-verify", action="store_true", help="Skip post-backup integrity verification")
    p_create.set_defaults(func=cmd_create)

    # Subcommand: verify
    p_verify = subparsers.add_parser("verify", help="Verify integrity of an existing backup file")
    p_verify.add_argument("path", type=str, help="Path to database backup file")
    p_verify.set_defaults(func=cmd_verify)

    # Subcommand: restore
    p_restore = subparsers.add_parser("restore", help="Restore database from a backup file")
    p_restore.add_argument("path", type=str, help="Path to database backup file to restore")
    p_restore.add_argument("--target", type=str, default=None, help="Target database path (default: active studio.db)")
    p_restore.add_argument("--no-safety", action="store_true", help="Skip creating safety copy of target database")
    p_restore.set_defaults(func=cmd_restore)

    # Subcommand: audit
    p_audit = subparsers.add_parser("audit", help="Audit existing backups in studio data directory")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
