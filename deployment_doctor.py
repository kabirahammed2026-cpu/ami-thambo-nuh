"""Deployment verification helper for CRM/Sales cloud rollouts.

Use this script after uploading a new zip build to validate that:
1) The served HTML points to reachable static JS/CSS bundles.
2) Optional backup archives can still be dry-run restored.

This is especially useful when troubleshooting browser errors like:
"TypeError: Failed to fetch dynamically imported module".
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-upload deployment verification helper.")
    parser.add_argument("--url", required=True, help="Public app URL, e.g. https://crm.example.com")
    parser.add_argument("--backup", help="Optional backup zip to dry-run verify with restore_from_backup.py")
    parser.add_argument("--app", choices=("crm", "sales"), help="Optional app hint for backup dry-run")
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
    if args.backup:
        backup_path = Path(args.backup).expanduser()
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
