import deployment_doctor as doctor


def test_extract_assets_dedupes_and_normalizes_urls():
    html = """
    <html><head>
      <link rel='stylesheet' href='/static/css/main.abc.css'>
      <script type='module' src='/static/js/index.123.js'></script>
      <script src='/static/js/index.123.js'></script>
      <script src='https://cdn.example.com/pkg.js'></script>
    </head></html>
    """
    assets = doctor._extract_assets(html, "https://crm.example.com/")
    assert assets == [
        "https://crm.example.com/static/css/main.abc.css",
        "https://crm.example.com/static/js/index.123.js",
        "https://cdn.example.com/pkg.js",
    ]


def test_extract_assets_ignores_data_urls_and_query_variants():
    html = """
    <script src='data:text/javascript,console.log(1)'></script>
    <script src='/static/js/index.123.js?v=1'></script>
    """
    assets = doctor._extract_assets(html, "https://crm.example.com/")
    assert assets == ["https://crm.example.com/static/js/index.123.js"]


def test_verify_storage_layout_flags_missing_expected_paths(tmp_path):
    problems = doctor._verify_storage_layout(tmp_path / "missing", "crm")
    assert any("Data dir does not exist" in item for item in problems)


def test_latest_backup_from_data_dir_prefers_newest_file(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    older = backup_dir / "ps_crm_backup_2026_04_01_000001.zip"
    newer = backup_dir / "ps_crm_backup_2026_04_02_000001.zip"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    latest = doctor._latest_backup_from_data_dir(tmp_path, "crm")
    assert latest == newer
