"""Restore CRM or Sales data from a backup archive."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from storage_paths import get_storage_dir
from ps_sales import load_config


CRM_EXPORT_MARKER = "exports/ps_crm.sql"
SALES_EXPORT_MARKER = "exports/ps_sales.sql"


def _detect_app(archive: zipfile.ZipFile) -> Optional[str]:
    names = set(archive.namelist())
    if CRM_EXPORT_MARKER in names:
        return "crm"
    if SALES_EXPORT_MARKER in names:
        return "sales"
    return None


def _crm_paths(data_dir_override: Optional[str]) -> tuple[Path, Path]:
    base_dir = (
        Path(data_dir_override).expanduser()
        if data_dir_override
        else Path(os.getenv("APP_STORAGE_DIR", get_storage_dir()))
    )
    db_path = Path(os.getenv("DB_PATH", str(base_dir / "ps_crm.db")))
    return base_dir, db_path


def _sales_paths(data_dir_override: Optional[str]) -> tuple[Path, Path]:
    if data_dir_override:
        data_dir = Path(data_dir_override).expanduser()
    else:
        data_dir = load_config().data_dir
    db_url = os.getenv("PS_SALES_DB_URL", "")
    prefix = "sqlite:///"
    if db_url:
        db_path = Path(db_url[len(prefix) :]) if db_url.startswith(prefix) else Path(db_url)
    else:
        db_path = data_dir / "ps_sales.db"
    return data_dir, db_path


def _copy_tree(source: Path, destination: Path) -> list[Path]:
    copied: list[Path] = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def _backup_existing_db(db_path: Path) -> Optional[Path]:
    if not db_path.exists():
        return None
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".bak_{timestamp}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore PS Business Suites data from a backup archive."
    )
    parser.add_argument("--backup", required=True, help="Path to the backup zip file")
    parser.add_argument(
        "--app",
        choices=("crm", "sales"),
        help="Specify the app type (crm or sales).",
    )
    parser.add_argument(
        "--data-dir",
        help="Override the data directory used for restore.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be restored without writing files.",
    )

    args = parser.parse_args()
    archive_path = Path(args.backup).expanduser()
    if not archive_path.exists():
        print(f"Backup archive not found: {archive_path}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(archive_path, "r") as archive:
        app = args.app or _detect_app(archive)
        if app is None:
            print(
                "Unable to detect app type from backup. Use --app crm|sales.",
                file=sys.stderr,
            )
            return 2

        data_dir, db_path = _crm_paths(args.data_dir) if app == "crm" else _sales_paths(args.data_dir)
        storage_prefix = Path("storage")
        db_prefix = Path("database")

        if args.dry_run:
            storage_files = [name for name in archive.namelist() if name.startswith("storage/")]
            db_files = [name for name in archive.namelist() if name.startswith("database/")]
            print(f"App: {app}")
            print(f"Data dir: {data_dir}")
            print(f"Database path: {db_path}")
            print(f"Storage files to restore: {len(storage_files)}")
            print(f"Database files in archive: {db_files}")
            return 0

        with tempfile.TemporaryDirectory() as tmpdir:
            archive.extractall(tmpdir)
            temp_root = Path(tmpdir)
            storage_dir = temp_root / storage_prefix
            db_dir = temp_root / db_prefix

            if db_dir.exists():
                db_candidates = sorted(db_dir.glob("*.db"))
            else:
                db_candidates = []

            if db_candidates:
                backup_path = _backup_existing_db(db_path)
                if backup_path:
                    print(f"Backed up existing database to {backup_path}")
                db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(db_candidates[0], db_path)
                print(f"Restored database to {db_path}")
            else:
                print("No database file found in archive; skipping DB restore.")

            if storage_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                copied = _copy_tree(storage_dir, data_dir)
                print(f"Restored {len(copied)} storage files into {data_dir}")
            else:
                print("No storage directory found in archive; skipping file restore.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
