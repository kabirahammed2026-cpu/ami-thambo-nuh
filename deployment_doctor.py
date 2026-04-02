"""Deployment verification helper for CRM/Sales cloud rollouts.

Use this script after uploading a new zip build to validate that:
1) The served HTML points to reachable static JS/CSS bundles.
2) Optional backup archives can still be dry-run restored.

This is especially useful when troubleshooting browser errors like:
"TypeError: Failed to fetch dynamically imported module".
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ASSET_LINK_PATTERN = re.compile(
    r"""(?:src|href)=[\"'](?P<asset>[^\"']+\.(?:js|css))(?:\?[^\"']*)?[\"']""",
    flags=re.IGNORECASE,
)


def _fetch(url: str, *, timeout: float = 8.0) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "ps-deployment-doctor/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        status = int(getattr(response, "status", 200) or 200)
        return status, body


def _fetch_status(url: str, *, timeout: float = 8.0) -> int:
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "ps-deployment-doctor/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(getattr(response, "status", 200) or 200)


def _extract_assets(html: str, base_url: str) -> list[str]:
    seen: set[str] = set()
    assets: list[str] = []
    for match in ASSET_LINK_PATTERN.finditer(html):
        candidate = (match.group("asset") or "").strip()
        if not candidate:
            continue
        if candidate.startswith("data:"):
            continue
        asset_url = urllib.parse.urljoin(base_url, candidate)
        if asset_url in seen:
            continue
        seen.add(asset_url)
        assets.append(asset_url)
    return assets


def _run_backup_dry_run(backup: Path, app: str | None) -> int:
    cmd = [
        sys.executable,
        "restore_from_backup.py",
        "--backup",
        str(backup),
        "--dry-run",
        "--strict-checksums",
    ]
    if app:
        cmd.extend(["--app", app])
    print("[doctor] Running backup restore dry-run:", " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def _latest_backup_from_data_dir(data_dir: Path, app: str) -> Path | None:
    backup_dir = data_dir / "backups"
    pattern = "ps_crm_backup_*.zip" if app == "crm" else "ps_sales_backup_*.zip"
    candidates = sorted(
        backup_dir.glob(pattern),
        key=lambda item: (item.stat().st_mtime, item.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _verify_storage_layout(data_dir: Path, app: str) -> list[str]:
    problems: list[str] = []
    if not data_dir.exists():
        problems.append(f"Data dir does not exist: {data_dir}")
        return problems
    if not data_dir.is_dir():
        problems.append(f"Data dir is not a directory: {data_dir}")
        return problems
    db_name = "ps_crm.db" if app == "crm" else "ps_sales.db"
    db_path = data_dir / db_name
    if not db_path.exists():
        problems.append(f"Database file missing: {db_path}")
    uploads_dir = data_dir / "uploads"
    if app == "crm" and not uploads_dir.exists():
        problems.append(f"Uploads directory missing: {uploads_dir}")
    backup_dir = data_dir / "backups"
    if not backup_dir.exists():
        problems.append(f"Backup directory missing: {backup_dir}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-upload deployment verification helper.")
    parser.add_argument("--url", required=True, help="Public app URL, e.g. https://crm.example.com")
    parser.add_argument("--backup", help="Optional backup zip to dry-run verify with restore_from_backup.py")
    parser.add_argument("--app", choices=("crm", "sales"), default="crm", help="App type for backup/data checks")
    parser.add_argument("--data-dir", help="Persistent app data dir (for Linode volume checks)")
    parser.add_argument(
        "--check-linode-flow",
        action="store_true",
        help="Validate Linode-style persistent data layout and auto-check latest backup in <data-dir>/backups.",
    )
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    base_url = args.url.rstrip("/") + "/"
    print(f"[doctor] Checking app root: {base_url}")
    try:
        status, html = _fetch(base_url, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"[doctor] FAIL: unable to load root URL ({exc})")
        return 2

    if status >= 400:
        print(f"[doctor] FAIL: root URL returned HTTP {status}")
        return 2

    assets = _extract_assets(html, base_url)
    if not assets:
        print("[doctor] WARN: no JS/CSS assets discovered in root HTML.")
    else:
        print(f"[doctor] Discovered {len(assets)} static asset link(s).")

    missing_assets: list[str] = []
    for asset_url in assets:
        try:
            asset_status = _fetch_status(asset_url, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            missing_assets.append(f"{asset_url} ({exc})")
            continue
        if asset_status >= 400:
            missing_assets.append(f"{asset_url} (HTTP {asset_status})")

    backup_result = 0
    backup_path: Path | None = Path(args.backup).expanduser() if args.backup else None
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else None

    if args.check_linode_flow:
        if data_dir is None:
            print("[doctor] FAIL: --check-linode-flow requires --data-dir")
            return 2
        problems = _verify_storage_layout(data_dir, args.app)
        if problems:
            print("[doctor] FAIL: persistent storage layout check failed:")
            for problem in problems:
                print(f"  - {problem}")
            return 2
        env_data_dir = os.getenv("APP_STORAGE_DIR")
        if args.app == "crm" and env_data_dir and Path(env_data_dir).expanduser() != data_dir:
            print(
                f"[doctor] FAIL: APP_STORAGE_DIR={env_data_dir} does not match expected --data-dir={data_dir}"
            )
            return 2
        if backup_path is None:
            backup_path = _latest_backup_from_data_dir(data_dir, args.app)
            if backup_path is None:
                print("[doctor] FAIL: no backup archive found in persistent backup directory.")
                return 2
            print(f"[doctor] Using latest backup archive: {backup_path}")

    if backup_path is not None:
        if not backup_path.exists():
            print(f"[doctor] FAIL: backup archive not found: {backup_path}")
            backup_result = 2
        else:
            backup_result = _run_backup_dry_run(backup_path, args.app)

    if missing_assets:
        print("[doctor] FAIL: missing/broken static assets:")
        for item in missing_assets:
            print(f"  - {item}")
        print(
            "[doctor] Likely cause: stale HTML cache points to old hashed bundle names. "
            "Clear CDN/reverse-proxy cache and hard-refresh browser after redeploy."
        )
        return 2

    if backup_result != 0:
        print("[doctor] FAIL: backup dry-run check did not pass.")
        return backup_result

    print("[doctor] PASS: static asset links and optional backup dry-run check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
