import render_bootstrap as rb


def test_extract_static_asset_paths_deduplicates_and_filters():
    html = '''
    <html><head>
      <link rel="stylesheet" href="/static/css/main.abc.css" />
      <script type="module" src="/static/js/index.123.js"></script>
      <script src="/static/js/index.123.js"></script>
      <script src="/foo/bar.js"></script>
    </head></html>
    '''
    assets = rb._extract_static_asset_paths(html)
    assert assets == ["/static/css/main.abc.css", "/static/js/index.123.js"]


def test_validate_streamlit_assets_checks_all_assets(monkeypatch):
    calls = []

    def fake_fetch_text(url: str, *, timeout: float = 3.0) -> str:
        calls.append(("html", url))
        return (
            "<script type='module' src='/static/js/index.abc.js'></script>"
            "<link rel='stylesheet' href='/static/css/main.abc.css'>"
        )

    def fake_fetch_status(url: str, *, timeout: float = 3.0) -> int:
        calls.append(("asset", url))
        return 200

    monkeypatch.setattr(rb, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(rb, "_fetch_status", fake_fetch_status)
    rb._validate_streamlit_assets("8501")

    asset_urls = [entry[1] for entry in calls if entry[0] == "asset"]
    assert any(url.endswith("/static/js/index.abc.js") for url in asset_urls)
    assert any(url.endswith("/static/css/main.abc.css") for url in asset_urls)


def test_validate_streamlit_assets_fails_if_process_exits_early(monkeypatch):
    class DeadProcess:
        def poll(self):
            return 23

    monkeypatch.setattr(rb, "_fetch_text", lambda *_args, **_kwargs: "")
    try:
        rb._validate_streamlit_assets("8501", process=DeadProcess())
    except RuntimeError as exc:
        assert "exit code 23" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError when process exits early")


def test_main_runs_validation_with_live_popen_process(monkeypatch):
    class FakeProcess:
        pid = 4321

        def poll(self):
            return None

        def wait(self):
            return 0

        def terminate(self):
            raise AssertionError("terminate should not be called on successful startup")

        def kill(self):
            raise AssertionError("kill should not be called on successful startup")

    fake_process = FakeProcess()
    calls = {"validated": 0}

    monkeypatch.setattr(rb.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("subprocess.run must not be used")))
    monkeypatch.setattr(rb.subprocess, "Popen", lambda *a, **k: fake_process)
    monkeypatch.setattr(rb, "_validate_streamlit_assets", lambda port, process=None: calls.update(validated=calls["validated"] + 1) or (process is fake_process))
    monkeypatch.setattr(rb, "_log", lambda _msg: None)
    monkeypatch.delenv("PS_SKIP_ASSET_VALIDATION", raising=False)
    monkeypatch.setenv("PORT", "8501")

    try:
        rb.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected main() to exit with process wait code")

    assert calls["validated"] == 1


def test_main_skips_validation_when_override_set(monkeypatch):
    class FakeProcess:
        pid = 5432

        def poll(self):
            return None

        def wait(self):
            return 0

        def terminate(self):
            raise AssertionError("terminate should not be called")

        def kill(self):
            raise AssertionError("kill should not be called")

    fake_process = FakeProcess()
    calls = {"validated": 0}

    monkeypatch.setattr(rb.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("subprocess.run must not be used")))
    monkeypatch.setattr(rb.subprocess, "Popen", lambda *a, **k: fake_process)
    monkeypatch.setattr(rb, "_validate_streamlit_assets", lambda *a, **k: calls.update(validated=calls["validated"] + 1))
    monkeypatch.setattr(rb, "_log", lambda _msg: None)
    monkeypatch.setenv("PS_SKIP_ASSET_VALIDATION", "1")
    monkeypatch.setenv("PORT", "8501")

    try:
        rb.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected main() to exit with process wait code")

    assert calls["validated"] == 0
