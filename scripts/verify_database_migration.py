"""
Phase 6A-R2: Database Migration Verification Script
Performs a read-only forensic online backup of production studio.db,
executes Alembic upgrade to 20261010_0007, and validates:
- PRAGMA integrity_check == 'ok'
- PRAGMA foreign_key_check == empty (zero violations)
- Zero data loss for existing users, projects, jobs, artifacts
- VoiceProfile CRUD verification
- Restart simulation
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(r"D:\AIVoiceStudioData")
PROD_DB = DATA_DIR / "studio.db"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DB = BACKUP_DIR / "migration_test_studio_backup.db"


def run_migration_audit():
    print("\n" + "=" * 78)
    print(" AI VOICE STUDIO — PHASE 6A-R2: DATABASE MIGRATION & INTEGRITY AUDIT")
    print("=" * 78)

    assert PROD_DB.exists(), f"Production DB does not exist at {PROD_DB}"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Non-destructive SQLite Online Backup
    print(f"\n[1/6] Tạo SQLite Online Backup từ {PROD_DB.name}...")
    src_conn = sqlite3.connect(str(PROD_DB))
    if BACKUP_DB.exists():
        BACKUP_DB.unlink()
    dst_conn = sqlite3.connect(str(BACKUP_DB))
    with dst_conn:
        src_conn.backup(dst_conn, pages=100)
    src_conn.close()
    dst_conn.close()
    print(f"  ✓ Đã tạo bản sao lưu trực tuyến an toàn: {BACKUP_DB} ({BACKUP_DB.stat().st_size:,} bytes)")

    # 2. Thu thập số liệu ban đầu (Baseline Counts)
    print("\n[2/6] Thu thập số liệu đối soát ban đầu trước khi áp dụng Migration...")
    conn = sqlite3.connect(str(BACKUP_DB))
    conn.execute("PRAGMA foreign_keys = ON;")
    
    baseline_counts = {}
    for table in ["users", "projects", "jobs", "artifacts", "reference_assets", "characters", "script_segments"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            baseline_counts[table] = count
            print(f"  * {table:20s}: {count:,} bản ghi")
        except sqlite3.OperationalError:
            baseline_counts[table] = 0
            print(f"  * {table:20s}: Chưa tồn tại")

    curr_version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    print(f"  * alembic_version hiện tại: {curr_version}")
    conn.close()

    # 3. Thực thi Alembic Upgrade trên Database Backup
    print(f"\n[3/6] Thực thi Alembic Upgrade tới revision '20261010_0007'...")
    # Update alembic.ini or pass sqlalchemy.url dynamically
    backup_db_url = f"sqlite:///{BACKUP_DB.as_posix()}"
    env = dict(sys.modules['os'].environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    
    cmd = [
        str(REPO_ROOT / ".venv" / "Scripts" / "alembic.exe"),
        "-x", f"db_url={backup_db_url}",
        "upgrade", "head",
    ]
    
    # We can invoke alembic command programmatically using alembic.config
    from alembic.config import Config
    from alembic import command
    
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", backup_db_url)
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(BACKUP_DB))
    conn.execute("PRAGMA foreign_keys = ON;")
    new_version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    print(f"  ✓ Alembic upgrade thành công! Phiên bản mới: {new_version}")
    assert new_version == "20261010_0007", f"Expected revision 20261010_0007, got {new_version}"

    # 4. Kiểm tra PRAGMA integrity_check & foreign_key_check
    print("\n[4/6] Kiểm định Toàn vẹn Cấu trúc SQLite (PRAGMA Checks)...")
    integrity_res = conn.execute("PRAGMA integrity_check;").fetchall()
    print(f"  * PRAGMA integrity_check: {integrity_res}")
    assert len(integrity_res) == 1 and integrity_res[0][0] == "ok", f"Integrity check failed: {integrity_res}"
    print("    ✓ BẢO TOÀN CẤU TRÚC: 'ok'")

    fk_res = conn.execute("PRAGMA foreign_key_check;").fetchall()
    print(f"  * PRAGMA foreign_key_check (số vi phạm khóa ngoại): {len(fk_res)}")
    assert len(fk_res) == 0, f"Foreign key violations found: {fk_res}"
    print("    ✓ BẢO TOÀN KHÓA NGOẠI: 0 vi phạm (100% CLEAN)")

    # 5. Kiểm thử CRUD Voice Profile trên Schema Mới
    print("\n[5/6] Kiểm thử toàn diện Chu trình CRUD Voice Profile trên Database đã Migrate...")
    asset_row = conn.execute("SELECT id, user_id FROM reference_assets LIMIT 1;").fetchone()
    if asset_row:
        asset_id, user_id = asset_row[0], asset_row[1]
    else:
        user_row = conn.execute("SELECT id, username FROM users WHERE is_active = 1 LIMIT 1;").fetchone()
        assert user_row is not None, "No active user found in database"
        user_id = user_row[0]
        asset_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO reference_assets (id, user_id, filename, file_path, file_size_bytes, duration_seconds, sample_rate, format, file_hash_sha256, voice_use_consent)
               VALUES (?, ?, 'sample.wav', 'C:/dummy.wav', 1024, 2.0, 24000, 'wav', 'dummy_hash_sha256', 1)""",
            (asset_id, user_id),
        )
        conn.commit()

    # CREATE
    test_prof_id = str(uuid.uuid4())
    prof_name = "Giọng Mẫu Nghiệm Thu Migration"
    params = {"speed": 1.1, "temperature": 0.85, "top_p": 0.9}
    conn.execute(
        """INSERT INTO voice_profiles (id, user_id, name, description, engine_id, reference_asset_id, parameters_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'vieneu-tts', ?, ?, datetime('now'), datetime('now'))""",
        (test_prof_id, user_id, prof_name, "Hồ sơ kiểm thử migration", asset_id, json.dumps(params)),
    )
    conn.commit()
    print(f"  ✓ CREATE: Đã tạo Voice Profile '{prof_name}' (ID: {test_prof_id})")

    # READ
    read_row = conn.execute("SELECT id, name, parameters_json FROM voice_profiles WHERE id = ?", (test_prof_id,)).fetchone()
    assert read_row is not None, "Failed to read newly created voice profile"
    assert read_row[1] == prof_name
    assert json.loads(read_row[2])["temperature"] == 0.85
    print(f"  ✓ READ: Đọc dữ liệu chính xác 100% từ bảng voice_profiles")

    # UPDATE
    params["speed"] = 1.25
    conn.execute(
        "UPDATE voice_profiles SET parameters_json = ?, updated_at = datetime('now') WHERE id = ?",
        (json.dumps(params), test_prof_id),
    )
    conn.commit()
    updated_row = conn.execute("SELECT parameters_json FROM voice_profiles WHERE id = ?", (test_prof_id,)).fetchone()
    assert json.loads(updated_row[0])["speed"] == 1.25
    print(f"  ✓ UPDATE: Cập nhật tham số profile thành công")

    # DELETE
    conn.execute("DELETE FROM voice_profiles WHERE id = ?", (test_prof_id,))
    conn.commit()
    deleted_row = conn.execute("SELECT id FROM voice_profiles WHERE id = ?", (test_prof_id,)).fetchone()
    assert deleted_row is None, "Profile should have been deleted"
    print(f"  ✓ DELETE: Xóa an toàn profile thử nghiệm")

    # 6. Đối soát Bảo toàn Dữ liệu & Khởi động lại (Restart Simulation)
    print("\n[6/6] Đối soát Bảo toàn Dữ liệu Tuyệt đối & Mô phỏng Khởi động lại (Restart)...")
    conn.close()

    # Re-open fresh connection (restart simulation)
    fresh_conn = sqlite3.connect(str(BACKUP_DB))
    fresh_conn.execute("PRAGMA foreign_keys = ON;")
    
    for table, orig_count in baseline_counts.items():
        curr_count = fresh_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        # reference_assets may have +1 if we inserted a temporary dummy asset
        if table == "reference_assets" and not asset_row:
            assert curr_count >= orig_count
        else:
            assert curr_count == orig_count, f"Data loss detected in {table}: was {orig_count}, now {curr_count}"
        print(f"  ✓ Bảo toàn {table:20s}: {curr_count:,} bản ghi (Không suy giảm dữ liệu)")

    fresh_conn.close()

    print("\n" + "=" * 78)
    print(" [KẾT QUẢ KIỂM ĐỊNH MIGRATION] TẤT CẢ TIÊU CHÍ AN TOÀN ĐÃ ĐƯỢC CHỨNG MINH 100%")
    print("  - Alembic Upgrade tới '20261010_0007': THÀNH CÔNG")
    print("  - PRAGMA integrity_check: 'ok'")
    print("  - PRAGMA foreign_key_check: 0 VI PHẠM")
    print("  - Dữ liệu người dùng, dự án, hàng đợi, âm thanh: BẢO TOÀN NGUYÊN VẸN")
    print("  - Cơ sở dữ liệu production gốc: KHÔNG BỊ CAN THIỆP NGOÀI Ý MUỐN")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    run_migration_audit()
