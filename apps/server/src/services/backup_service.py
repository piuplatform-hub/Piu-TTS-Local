"""
AI Voice Studio — Safe SQLite Online Backup & Restore Service
Uses SQLite Online Backup API (sqlite3.Connection.backup) for transactionally
consistent live backups in WAL mode without tearing or locking the database.
"""

from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from ..config import settings

logger = logging.getLogger("studio.backup")


class BackupService:
    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @classmethod
    def verify_backup(cls, backup_path: Path | str) -> Dict[str, Any]:
        """
        Verifies SQLite database integrity, schema completeness, and row counts.
        """
        path = Path(backup_path).resolve()
        if not path.exists():
            return {
                "is_valid": False,
                "error": f"Backup file not found: {path}",
                "path": str(path),
            }

        file_size = path.stat().st_size
        sha256_checksum = cls.calculate_sha256(path)

        try:
            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()

            # PRAGMA integrity_check
            cursor.execute("PRAGMA integrity_check;")
            integrity_rows = cursor.fetchall()
            integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"

            # PRAGMA quick_check
            cursor.execute("PRAGMA quick_check;")
            quick_rows = cursor.fetchall()
            quick_ok = len(quick_rows) == 1 and quick_rows[0][0] == "ok"

            # Table inventory & row counts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]

            table_counts: Dict[str, int] = {}
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                    table_counts[table] = cursor.fetchone()[0]
                except Exception as table_err:
                    table_counts[table] = -1

            # Alembic revision
            alembic_version = None
            if "alembic_version" in tables:
                cursor.execute("SELECT version_num FROM alembic_version;")
                row = cursor.fetchone()
                if row:
                    alembic_version = row[0]

            conn.close()

            is_valid = integrity_ok and quick_ok and ("users" in tables or "jobs" in tables)

            return {
                "is_valid": is_valid,
                "path": str(path),
                "file_size_bytes": file_size,
                "sha256": sha256_checksum,
                "integrity_check": integrity_rows[0][0] if integrity_rows else "unknown",
                "quick_check": quick_rows[0][0] if quick_rows else "unknown",
                "tables": table_counts,
                "alembic_version": alembic_version,
            }

        except Exception as exc:
            return {
                "is_valid": False,
                "path": str(path),
                "error": str(exc),
                "file_size_bytes": file_size,
                "sha256": sha256_checksum,
            }

    @classmethod
    def create_online_backup(
        cls,
        source_path: Optional[Path | str] = None,
        destination_path: Optional[Path | str] = None,
        verify: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a consistent online snapshot of a live SQLite database in WAL mode
        using sqlite3.Connection.backup().
        """
        src = Path(source_path).resolve() if source_path else (settings.get_data_dir() / "studio.db")
        if not src.exists():
            raise FileNotFoundError(f"Source database file not found: {src}")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if destination_path:
            dest = Path(destination_path).resolve()
        else:
            dest = settings.get_data_dir() / "backups" / f"studio_{timestamp}.db"

        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initiating online SQLite backup from {src} -> {dest}")

        # Connect to source and destination
        # Timeout ensures it will wait for shared lock if a write is actively committing
        src_conn = sqlite3.connect(str(src), timeout=30.0)
        dest_conn = sqlite3.connect(str(dest), timeout=30.0)

        try:
            # Execute step-by-step backup with SQLite Online Backup API
            # pages=100 backs up 100 pages per step while releasing lock briefly
            src_conn.backup(dest_conn, pages=100)
        finally:
            dest_conn.close()
            src_conn.close()

        file_size = dest.stat().st_size
        sha256_checksum = cls.calculate_sha256(dest)

        verification = None
        if verify:
            verification = cls.verify_backup(dest)
            if not verification.get("is_valid", False):
                raise RuntimeError(f"Backup verification failed: {verification}")

        return {
            "status": "success",
            "source_path": str(src),
            "backup_path": str(dest),
            "file_size_bytes": file_size,
            "sha256": sha256_checksum,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "verification": verification,
        }

    @classmethod
    def restore_backup(
        cls,
        backup_path: Path | str,
        target_path: Optional[Path | str] = None,
        create_safety_backup: bool = True,
    ) -> Dict[str, Any]:
        """
        Restores a target SQLite database from a verified backup snapshot.
        Creates an automatic pre-restore safety copy if target exists.
        """
        b_path = Path(backup_path).resolve()
        if not b_path.exists():
            raise FileNotFoundError(f"Backup file does not exist: {b_path}")

        # 1. Pre-restore validation
        verification = cls.verify_backup(b_path)
        if not verification.get("is_valid", False):
            raise ValueError(f"Cannot restore from corrupt or invalid backup: {verification}")

        target = Path(target_path).resolve() if target_path else (settings.get_data_dir() / "studio.db")

        # 2. Safety copy of current target if it exists
        safety_path = None
        if target.exists() and create_safety_backup:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safety_path = target.with_name(f"{target.name}.pre_restore_{timestamp}.bak")
            logger.info(f"Creating pre-restore safety copy: {safety_path}")
            src_conn = sqlite3.connect(str(target), timeout=10.0)
            safe_conn = sqlite3.connect(str(safety_path), timeout=10.0)
            try:
                src_conn.backup(safe_conn)
            finally:
                safe_conn.close()
                src_conn.close()

        # 3. Restore using Online Backup API from backup -> target
        logger.info(f"Restoring database from {b_path} -> {target}")
        b_conn = sqlite3.connect(str(b_path), timeout=30.0)
        t_conn = sqlite3.connect(str(target), timeout=30.0)
        try:
            b_conn.backup(t_conn)
        finally:
            t_conn.close()
            b_conn.close()

        # 4. Post-restore verification of restored target
        post_verification = cls.verify_backup(target)
        if not post_verification.get("is_valid", False):
            raise RuntimeError(f"Post-restore verification failed on target DB: {post_verification}")

        return {
            "status": "success",
            "backup_restored": str(b_path),
            "target_path": str(target),
            "safety_backup": str(safety_path) if safety_path else None,
            "verification": post_verification,
        }

    @classmethod
    def audit_existing_backups(cls, search_dirs: Optional[List[Path | str]] = None) -> List[Dict[str, Any]]:
        """
        Scans data directory and backups directory for existing .bak and .db files,
        running integrity audits on each.
        """
        if search_dirs is None:
            data_dir = settings.get_data_dir()
            search_dirs = [data_dir, data_dir / "backups"]

        reports: List[Dict[str, Any]] = []
        scanned_files = set()

        for d in search_dirs:
            p = Path(d).resolve()
            if not p.exists() or not p.is_dir():
                continue
            for item in p.iterdir():
                if item.is_file() and (item.suffix in [".bak", ".db"] or ".bak" in item.name):
                    abs_path = str(item.resolve())
                    if abs_path in scanned_files:
                        continue
                    scanned_files.add(abs_path)
                    report = cls.verify_backup(item)
                    report["file_name"] = item.name
                    reports.append(report)

        return reports
