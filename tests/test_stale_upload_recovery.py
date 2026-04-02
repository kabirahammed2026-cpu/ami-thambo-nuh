import app


class _DummyStreamlit:
    def __init__(self):
        self.session_state = {}


class _StaleUpload:
    name = "stale.pdf"
    size = 32

    def getvalue(self):
        raise RuntimeError("MediaFileStorageError: No media file with id deadbeef")


def test_read_uploaded_bytes_returns_empty_for_stale_media(monkeypatch):
    monkeypatch.setattr(app, "st", _DummyStreamlit())
    assert app._read_uploaded_bytes(_StaleUpload()) == b""


def test_extract_text_from_quotation_upload_handles_stale_media(monkeypatch):
    monkeypatch.setattr(app, "st", _DummyStreamlit())
    text, warnings = app._extract_text_from_quotation_upload(_StaleUpload(), use_cache=False)
    assert text == ""
    assert any("no longer available" in warning.lower() for warning in warnings)


def test_read_import_dataframe_handles_stale_media(monkeypatch):
    monkeypatch.setattr(app, "st", _DummyStreamlit())
    dataframe, notes = app._read_import_dataframe(_StaleUpload())
    assert dataframe is None
    assert any("no longer available" in note.lower() for note in notes)


def test_clear_stale_upload_state_removes_widget_and_derived_state(monkeypatch):
    dummy_st = _DummyStreamlit()
    dummy_st.session_state.update(
        {
            "quotation_prefill_upload": object(),
            "quotation_prefill_token": "abc",
            "_upload_bytes_cache": {"x": b"1"},
        }
    )
    monkeypatch.setattr(app, "st", dummy_st)
    app._clear_stale_upload_state(
        widget_keys=["quotation_prefill_upload"],
        state_keys=["quotation_prefill_token"],
    )
    assert "quotation_prefill_upload" not in dummy_st.session_state
    assert "quotation_prefill_token" not in dummy_st.session_state
    assert "_upload_bytes_cache" not in dummy_st.session_state
