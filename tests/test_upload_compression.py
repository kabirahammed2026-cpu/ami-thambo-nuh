from pathlib import Path

from PIL import Image

import app


class DummyUpload:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self.size = len(payload)

    def getvalue(self) -> bytes:
        return self._payload


def _make_large_jpeg(width: int = 3500, height: int = 2600, *, quality: int = 96) -> bytes:
    image = Image.effect_noise((width, height), 120).convert("RGB")
    # Add extra detail so compression has real work to do.
    for x in range(0, width, 250):
        image.putpixel((x, min(height - 1, x % height)), (255, 0, 0))
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def test_save_uploaded_file_compresses_large_jpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "MAX_UPLOAD_BYTES", 180_000)
    monkeypatch.setattr(app, "UPLOAD_IMAGE_MAX_DIMENSION", 1000)
    monkeypatch.setattr(app, "UPLOAD_IMAGE_JPEG_QUALITY", 55)

    target_dir = tmp_path / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)

    source = _make_large_jpeg()
    assert len(source) > app.MAX_UPLOAD_BYTES

    saved = app.save_uploaded_file(
        DummyUpload("huge-photo.jpg", source),
        target_dir,
        allowed_extensions={".jpg", ".jpeg"},
    )

    assert saved is not None
    written = Path(saved)
    assert written.exists()
    assert written.stat().st_size <= app.MAX_UPLOAD_BYTES


def test_save_uploaded_file_rejects_when_still_too_large(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "MAX_UPLOAD_BYTES", 20_000)
    monkeypatch.setattr(app, "UPLOAD_IMAGE_MAX_DIMENSION", 3200)
    monkeypatch.setattr(app, "UPLOAD_IMAGE_JPEG_QUALITY", 95)

    target_dir = tmp_path / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)

    source = _make_large_jpeg(2400, 1800, quality=98)
    saved = app.save_uploaded_file(
        DummyUpload("too-large.jpg", source),
        target_dir,
        allowed_extensions={".jpg", ".jpeg"},
    )

    assert saved is None


def test_validate_upload_allows_oversized_compressible_file_for_standardization(monkeypatch):
    monkeypatch.setattr(app, "MAX_UPLOAD_BYTES", 50_000)
    source = _make_large_jpeg(1600, 1200, quality=95)
    err = app._validate_upload(
        DummyUpload("compress-me.jpg", source),
        allowed_extensions={".jpg", ".jpeg"},
        max_bytes=app.MAX_UPLOAD_BYTES,
    )
    assert err is None
