"""Restore CRM or Sales data from a backup archive."""
from __future__ import annotations

import argparse
import hashlib
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
CRM_DB_MARKERS = ("database/ps_crm.db", "ps_crm.db")
SALES_DB_MARKERS = ("database/ps_sales.db", "ps_sales.db")
STORAGE_PREFIX_CANDIDATES = ("storage", "uploads", "files")


def _detect_app(archive: zipfile.ZipFile) -> Optional[str]:
    names = set(archive.namelist())
    if CRM_EXPORT_MARKER in names:
        return "crm"
    if SALES_EXPORT_MARKER in names:
        return "sales"
    if any(marker in names for marker in CRM_DB_MARKERS):
        return "crm"
    if any(marker in names for marker in SALES_DB_MARKERS):
        return "sales"
    return None


def _crm_paths(data_dir_override: Optional[str]) -> tuple[Path, Path]:
    if data_dir_override:
        base_dir = Path(data_dir_override).expanduser()
        db_path = base_dir / "ps_crm.db"
    else:
        base_dir = Path(os.getenv("APP_STORAGE_DIR", get_storage_dir()))
        db_path = Path(os.getenv("DB_PATH", str(base_dir / "ps_crm.db")))
    return base_dir, db_path


def _sales_paths(data_dir_override: Optional[str]) -> tuple[Path, Path]:
    if data_dir_override:
        data_dir = Path(data_dir_override).expanduser()
        db_path = data_dir / "ps_sales.db"
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




def _safe_extract_archive(archive: zipfile.ZipFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.infolist():
        member_path = destination / member.filename
        try:
            member_resolved = member_path.resolve()
            member_resolved.relative_to(destination_resolved)
        except OSError as exc:
            raise RuntimeError(f"Invalid archive member path: {member.filename}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Unsafe archive member blocked: {member.filename}") from exc
    archive.extractall(destination)


def _select_db_candidate(db_dir: Path, app: str) -> Optional[Path]:
    expected_name = "ps_crm.db" if app == "crm" else "ps_sales.db"
    expected = db_dir / expected_name
    if expected.exists():
        return expected
    db_candidates = sorted(db_dir.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not db_candidates:
        return None
    return db_candidates[0]


def _select_db_candidate_from_archive(temp_root: Path, app: str) -> Optional[Path]:
    db_dir = temp_root / "database"
    selected = _select_db_candidate(db_dir, app) if db_dir.exists() else None
    if selected is not None:
        return selected
    expected_name = "ps_crm.db" if app == "crm" else "ps_sales.db"
    direct_match = next(
        (
            candidate
            for candidate in temp_root.rglob(expected_name)
            if candidate.is_file()
        ),
        None,
    )
    if direct_match is not None:
        return direct_match
    db_candidates = sorted(
        (candidate for candidate in temp_root.rglob("*.db") if candidate.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return db_candidates[0] if db_candidates else None


def _resolve_storage_root(temp_root: Path) -> Optional[Path]:
    for prefix in STORAGE_PREFIX_CANDIDATES:
        candidate = temp_root / prefix
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _verify_archive_checksums(archive: zipfile.ZipFile) -> tuple[int, int]:
    try:
        checksum_blob = archive.read("checksums.txt")
    except KeyError:
        return 0, 0
    expected_lines = [
        line.strip()
        for line in checksum_blob.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    verified = 0
    mismatches = 0
    for line in expected_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        expected_hash, entry_name = parts
        try:
            payload = archive.read(entry_name)
        except KeyError:
            mismatches += 1
            continue
        actual_hash = hashlib.sha256(payload).hexdigest()
        verified += 1
        if actual_hash != expected_hash:
            mismatches += 1
    return verified, mismatches


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
    parser.add_argument(
        "--strict-checksums",
        action="store_true",
        help="Abort restore when checksums.txt exists and any mismatch is detected.",
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
        verified_checksums, checksum_mismatches = _verify_archive_checksums(archive)
        if verified_checksums:
            status = f"Checksum verification: {verified_checksums} file(s) checked"
            if checksum_mismatches:
                status += f", mismatches={checksum_mismatches}"
            print(status)
            if args.strict_checksums and checksum_mismatches:
                print("Checksum mismatches detected; aborting due to --strict-checksums.", file=sys.stderr)
                return 2

        if args.dry_run:
            storage_files = [
                name
                for name in archive.namelist()
                if any(name.startswith(f"{prefix}/") for prefix in STORAGE_PREFIX_CANDIDATES)
            ]
            db_files = [name for name in archive.namelist() if name.endswith(".db")]
            print(f"App: {app}")
            print(f"Data dir: {data_dir}")
            print(f"Database path: {db_path}")
            print(f"Storage files to restore: {len(storage_files)}")
            print(f"Database files in archive: {db_files}")
            return 0

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            _safe_extract_archive(archive, temp_root)
            storage_dir = _resolve_storage_root(temp_root)
            selected_db = _select_db_candidate_from_archive(temp_root, app)

            if selected_db is not None:
                backup_path = _backup_existing_db(db_path)
                if backup_path:
                    print(f"Backed up existing database to {backup_path}")
                db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(selected_db, db_path)
                print(f"Restored database to {db_path}")
            else:
                print("No database file found in archive; skipping DB restore.")

            if storage_dir is not None and storage_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                copied = _copy_tree(storage_dir, data_dir)
                print(f"Restored {len(copied)} storage files into {data_dir}")
            else:
                print("No storage directory found in archive; skipping file restore.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
