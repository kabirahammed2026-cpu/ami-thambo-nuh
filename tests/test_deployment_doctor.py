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
