from pathlib import Path


def test_advanced_search_applies_sql_date_window_before_limit():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "def _date_range_sql(" in source
    assert "date(COALESCE(q.quote_date, q.created_at)) BETWEEN date(?) AND date(?)" in source
    assert '"COALESCE(service_start_date, service_end_date)"' in source
    assert '"COALESCE(maintenance_start_date, maintenance_end_date)"' in source
    assert '_date_range_sql("created_at")' in source
    assert '_date_range_sql("created_at", include_where=True)' in source


def test_advanced_search_includes_staff_owner_fields_for_service_and_maintenance():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "SELECT service_id, description, service_start_date, service_end_date, service_product_info, status, created_by" in source
    assert "SELECT maintenance_id, description, maintenance_start_date, maintenance_end_date, maintenance_product_info, status, created_by" in source
