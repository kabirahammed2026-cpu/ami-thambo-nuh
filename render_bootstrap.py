"""Production-friendly bootstrapper for Render and Railway deployments.

This module mirrors the ``Procfile`` command while allowing platforms that
expect a Python entry point (e.g. ``python render_bootstrap.py``) to launch the
Streamlit application. It automatically selects the service or sales
experience based on environment variables and prefers persistent storage
mounts when available.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_APP_SCRIPT = "main.py"
SALES_APP_SCRIPT = "sales_app.py"
ASSET_VALIDATION_TIMEOUT_SECONDS = 25.0
ASSET_VALIDATION_INTERVAL_SECONDS = 0.4
ASSET_LINK_PATTERN = re.compile(
    r"""(?:src|href)=["'](?P<asset>/static/[^"']+\.(?:js|css))["']""",
    flags=re.IGNORECASE,
)


def _log(message: str) -> None:
    """Emit an operator-visible bootstrap log line."""

    print(f"[render_bootstrap] {message}", file=sys.stderr, flush=True)


def _select_app_script() -> str:
    """Return the Streamlit script that should be executed."""

    explicit_script = os.getenv("PS_APP_SCRIPT")
    if explicit_script:
        return explicit_script

    app_flavor = os.getenv("PS_APP", "").lower()
    if app_flavor in {"sales", "sales_app"}:
        return SALES_APP_SCRIPT

    return DEFAULT_APP_SCRIPT


def _preferred_storage_dir() -> Path | None:
    """Return a writable directory for application data if one is obvious."""

    configured_dir = os.getenv("APP_STORAGE_DIR")
    if configured_dir:
        return Path(configured_dir)

    for candidate in (os.getenv("RAILWAY_VOLUME_MOUNT_PATH"), "/data", "/opt/render/project/.data"):
        if candidate and Path(candidate).exists():
            return Path(candidate)

    return None


def _extract_static_asset_paths(html: str) -> list[str]:
    """Extract Streamlit static asset paths from bootstrap HTML."""

    if not html:
        return []
    seen: set[str] = set()
    assets: list[str] = []
    for match in ASSET_LINK_PATTERN.finditer(html):
        asset = match.group("asset")
        if asset in seen:
            continue
        seen.add(asset)
        assets.append(asset)
    return assets


def _fetch_text(url: str, *, timeout: float = 3.0) -> str:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_status(url: str, *, timeout: float = 3.0) -> int:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(getattr(response, "status", 200) or 200)


def _validate_streamlit_assets(
    port: str, *, process: subprocess.Popen | None = None
) -> bool:
    """Best-effort startup validation without hard-failing on HTML shape changes."""

    base_url = f"http://127.0.0.1:{port}"
    health_url = urllib.parse.urljoin(base_url, "/_stcore/health")
    deadline = time.monotonic() + ASSET_VALIDATION_TIMEOUT_SECONDS
    last_error = "application bootstrap did not become reachable"
    while time.monotonic() < deadline:
        if process is not None:
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"streamlit exited before startup validation completed (exit code {return_code})"
                )
        try:
            # Streamlit health endpoint is the most stable readiness signal.
            try:
                status = _fetch_status(health_url, timeout=2.5)
                if status < 400:
                    return True
            except Exception:
                pass

            html = _fetch_text(base_url, timeout=2.5)
            assets = _extract_static_asset_paths(html)
            # HTML can change between Streamlit releases. Once the app root is
            # reachable we treat startup as healthy, and only probe assets as
            # a non-fatal diagnostic when links are discoverable.
            if assets:
                missing: list[str] = []
                for asset in assets:
                    asset_url = urllib.parse.urljoin(base_url, asset)
                    try:
                        status = _fetch_status(asset_url, timeout=2.5)
                    except urllib.error.URLError as exc:
                        missing.append(f"{asset} ({exc})")
                        continue
                    if status >= 400:
                        missing.append(f"{asset} (HTTP {status})")
                if missing:
                    _log("Asset probe warning: " + ", ".join(missing))
            if "<html" in html.lower() or "streamlit" in html.lower():
                return True
        except Exception as exc:
            last_error = str(exc)
            time.sleep(ASSET_VALIDATION_INTERVAL_SECONDS)
    _log(
        "Startup validation warning (continuing without fail-fast): "
        + last_error
    )
    return False


def main() -> None:
    root_dir = Path(__file__).resolve().parent

    app_script_name = _select_app_script()
    app_script = root_dir / app_script_name
    if not app_script.exists():
        raise SystemExit(
            f"Expected application script '{app_script_name}' next to render_bootstrap.py, but it was not found."
        )

    storage_dir = _preferred_storage_dir()
    if storage_dir is not None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        if app_script_name == SALES_APP_SCRIPT:
            sales_storage = storage_dir / "ps-sales"
            sales_storage.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("PS_SALES_DATA_DIR", str(sales_storage))
        else:
            crm_storage = storage_dir / "ps-business-suites"
            crm_storage.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("APP_STORAGE_DIR", str(crm_storage))

    os.environ.setdefault("BROWSER", "none")
    os.environ["STREAMLIT_THEME_BASE"] = "light"
    os.environ["STREAMLIT_THEME_TEXTCOLOR"] = "#111827"
    os.environ["STREAMLIT_THEME_BACKGROUNDCOLOR"] = "#FFFFFF"
    os.environ["STREAMLIT_THEME_SECONDARYBACKGROUNDCOLOR"] = "#FFFFFF"
    os.environ["STREAMLIT_THEME_PRIMARYCOLOR"] = "#1d3b64"

    port = (os.getenv("PORT", "8501") or "8501").strip() or "8501"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_script),
        "--server.port",
        str(port),
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
    ]

    skip_validation = os.getenv("PS_SKIP_ASSET_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    process = subprocess.Popen(command, cwd=root_dir)
    _log(f"Started Streamlit process (pid={process.pid}) on port {port}.")
    if not skip_validation:
        _log("Validating startup readiness (best effort).")
        try:
            validated = _validate_streamlit_assets(str(port), process=process)
            if validated:
                _log("Startup readiness validation passed.")
            else:
                _log("Startup readiness validation timed out; continuing with running process.")
        except Exception as exc:
            _log(f"Startup readiness validation warning: {exc}. Continuing.")
    raise SystemExit(process.wait())


if __name__ == "__main__":
    main()
