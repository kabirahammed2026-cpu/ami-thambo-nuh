from datetime import datetime
from types import SimpleNamespace

import app
import sqlite3
import pytest


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    app.init_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def test_push_runtime_notification_dedupes_by_dedupe_key(monkeypatch):
    fake_st = SimpleNamespace(session_state={}, query_params={})
    monkeypatch.setattr(app, "st", fake_st)
    app.push_runtime_notification(
        "Quotation uploaded",
        "Q-101 uploaded",
        dedupe_key="quotation_upload:101",
    )
    app.push_runtime_notification(
        "Quotation uploaded",
        "Q-101 uploaded again",
        dedupe_key="quotation_upload:101",
    )
    buffer = fake_st.session_state.get(app.NOTIFICATION_BUFFER_KEY) or []
    assert len(buffer) == 1


def test_upsert_reminder_updates_existing_row_with_latest_date(conn):
    initial = datetime(2026, 3, 20, 10, 0)
    updated = datetime(2026, 4, 1, 11, 30)
    app.upsert_reminder(
        conn,
        entity_type="report",
        entity_id=77,
        remind_at=initial,
        message="Old reminder",
        source_text="20.03.2026",
    )
    app.upsert_reminder(
        conn,
        entity_type="report",
        entity_id=77,
        remind_at=updated,
        message="Updated reminder",
        source_text="01.04.2026",
    )
    row = conn.execute(
        "SELECT remind_at, message, source_text FROM reminders WHERE entity_type='report' AND entity_id=77"
    ).fetchone()
    assert row is not None
    assert "2026-04-01 11:30" in str(row[0])
    assert row[1] == "Updated reminder"
    assert row[2] == "01.04.2026"


def test_normalize_report_window_preserves_selected_month_range():
    key, start_date, end_date = app.normalize_report_window(
        "monthly",
        "2026-04-01",
        "2026-04-30",
    )
    assert key == "monthly"
    assert start_date.isoformat() == "2026-04-01"
    assert end_date.isoformat() == "2026-04-30"
