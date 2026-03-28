import time

import app


class CountingUpload:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self.size = len(payload)
        self._payload = payload
        self.calls = 0

    def getvalue(self) -> bytes:
        self.calls += 1
        return self._payload


def test_read_uploaded_bytes_uses_session_cache():
    app.st.session_state.clear()
    upload = CountingUpload("quote.pdf", b"sample-payload")

    first = app._read_uploaded_bytes(upload)
    second = app._read_uploaded_bytes(upload)

    assert first == b"sample-payload"
    assert second == b"sample-payload"
    assert upload.calls == 1


def test_cached_health_warnings_respects_ttl(monkeypatch):
    app.st.session_state.clear()
    calls = {"count": 0}

    def fake_run_health_checks(_conn):
        calls["count"] += 1
        return [f"warn-{calls['count']}"]

    monkeypatch.setattr(app, "run_health_checks", fake_run_health_checks)
    conn = object()

    first = app.get_cached_health_warnings(conn)
    second = app.get_cached_health_warnings(conn)

    assert first == ["warn-1"]
    assert second == ["warn-1"]
    assert calls["count"] == 1

    app.st.session_state["_health_check_last_ts"] = (
        time.monotonic() - app.HEALTH_CHECK_CACHE_TTL_SECONDS - 1
    )
    third = app.get_cached_health_warnings(conn)
    assert third == ["warn-2"]
    assert calls["count"] == 2
