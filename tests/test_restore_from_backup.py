import io
import zipfile

import restore_from_backup as rfb


def _archive_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    return buffer.getvalue()


def test_detect_app_uses_database_markers_when_export_missing():
    payload = _archive_bytes({"database/ps_crm.db": b"sqlite"})
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        assert rfb._detect_app(archive) == "crm"


def test_verify_archive_checksums_reports_mismatch_count():
    payload = _archive_bytes(
        {
            "database/ps_sales.db": b"db-bytes",
            "checksums.txt": b"deadbeef database/ps_sales.db\n",
        }
    )
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        verified, mismatches = rfb._verify_archive_checksums(archive)
    assert verified == 1
    assert mismatches == 1


def test_verify_archive_checksums_returns_zero_when_file_missing():
    payload = _archive_bytes({"database/ps_sales.db": b"db-bytes"})
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        verified, mismatches = rfb._verify_archive_checksums(archive)
    assert (verified, mismatches) == (0, 0)
