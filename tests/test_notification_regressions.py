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


def test_build_reminder_alerts_keeps_staff_isolated_to_their_own_reports(conn, monkeypatch):
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff1_case', 'x', 'staff')"
    )
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff2_case', 'x', 'staff')"
    )
    staff1_id = conn.execute("SELECT user_id FROM users WHERE username='staff1_case'").fetchone()[0]
    staff2_id = conn.execute("SELECT user_id FROM users WHERE username='staff2_case'").fetchone()[0]
    conn.execute(
        """
        INSERT INTO work_reports (report_id, user_id, period_type, period_start, period_end, tasks, remarks, research)
        VALUES (101, ?, 'daily', '2026-04-01', '2026-04-01', '', '', '')
        """,
        (staff1_id,),
    )
    conn.execute(
        """
        INSERT INTO work_reports (report_id, user_id, period_type, period_start, period_end, tasks, remarks, research)
        VALUES (102, ?, 'daily', '2026-04-01', '2026-04-01', '', '', '')
        """,
        (staff2_id,),
    )
    app.upsert_reminder(
        conn,
        entity_type="report",
        entity_id=101,
        remind_at=datetime(2026, 4, 2, 9, 0),
        message="r1",
    )
    app.upsert_reminder(
        conn,
        entity_type="report",
        entity_id=102,
        remind_at=datetime(2026, 4, 2, 10, 0),
        message="r2",
    )
    conn.commit()

    monkeypatch.setattr(app, "get_current_user", lambda: {"user_id": staff1_id, "role": "staff"})
    monkeypatch.setattr(app, "current_user_id", lambda: staff1_id)
    monkeypatch.setattr(app, "accessible_customer_ids", lambda _conn: set())

    alerts = app._build_reminder_alerts(conn, limit=10)
    report_links = [item.get("deep_link", {}).get("record_id") for item in alerts]
    assert report_links == ["101"]


def test_build_reminder_alerts_allows_admin_to_see_report_reminders(conn, monkeypatch):
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff_a_case', 'x', 'staff')"
    )
    staff_id = conn.execute("SELECT user_id FROM users WHERE username='staff_a_case'").fetchone()[0]
    conn.execute(
        """
        INSERT INTO work_reports (report_id, user_id, period_type, period_start, period_end, tasks, remarks, research)
        VALUES (301, ?, 'daily', '2026-04-01', '2026-04-01', '', '', '')
        """,
        (staff_id,),
    )
    app.upsert_reminder(
        conn,
        entity_type="report",
        entity_id=301,
        remind_at=datetime(2026, 4, 2, 9, 0),
        message="admin-visible",
    )
    conn.commit()

    monkeypatch.setattr(app, "get_current_user", lambda: {"user_id": 999, "role": "admin"})
    monkeypatch.setattr(app, "current_user_id", lambda: 999)

    alerts = app._build_reminder_alerts(conn, limit=10)
    report_links = [item.get("deep_link", {}).get("record_id") for item in alerts]
    assert "301" in report_links


def test_upsert_work_report_refreshes_report_reminder_date(conn):
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff_reminder_case', 'x', 'staff')"
    )
    user_id = conn.execute(
        "SELECT user_id FROM users WHERE username='staff_reminder_case'"
    ).fetchone()[0]

    report_id = app.upsert_work_report(
        conn,
        report_id=None,
        user_id=int(user_id),
        period_type="daily",
        period_start="2026-04-01",
        period_end="2026-04-01",
        tasks="",
        remarks="",
        research="",
        report_template="service",
        grid_rows=[{"customer_name": "A", "reminder_date": "2026-04-05"}],
    )
    app.upsert_work_report(
        conn,
        report_id=int(report_id),
        user_id=int(user_id),
        period_type="daily",
        period_start="2026-04-01",
        period_end="2026-04-01",
        tasks="",
        remarks="",
        research="",
        report_template="service",
        grid_rows=[{"customer_name": "A", "reminder_date": "2026-04-12"}],
    )
    row = conn.execute(
        "SELECT remind_at, source_text FROM reminders WHERE entity_type='report' AND entity_id=?",
        (int(report_id),),
    ).fetchone()
    assert row is not None
    assert "2026-04-12" in str(row[0])
    assert row[1] == "2026-04-12"


def test_build_staff_alerts_keeps_staff_report_reminders_private(conn, monkeypatch):
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff_private_a', 'x', 'staff')"
    )
    conn.execute(
        "INSERT INTO users (username, pass_hash, role) VALUES ('staff_private_b', 'x', 'staff')"
    )
    staff_a = conn.execute(
        "SELECT user_id FROM users WHERE username='staff_private_a'"
    ).fetchone()[0]
    staff_b = conn.execute(
        "SELECT user_id FROM users WHERE username='staff_private_b'"
    ).fetchone()[0]
    report_a = app.upsert_work_report(
        conn,
        report_id=None,
        user_id=int(staff_a),
        period_type="daily",
        period_start="2026-04-01",
        period_end="2026-04-01",
        tasks="",
        remarks="",
        research="",
        report_template="service",
        grid_rows=[{"customer_name": "A", "reminder_date": "2026-04-09"}],
    )
    report_b = app.upsert_work_report(
        conn,
        report_id=None,
        user_id=int(staff_b),
        period_type="daily",
        period_start="2026-04-02",
        period_end="2026-04-02",
        tasks="",
        remarks="",
        research="",
        report_template="service",
        grid_rows=[{"customer_name": "B", "reminder_date": "2026-04-10"}],
    )
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    alerts = app._build_staff_alerts(conn, user_id=int(staff_a))
    deep_records = {
        (entry.get("deep_link") or {}).get("record_id")
        for entry in alerts
        if isinstance(entry.get("deep_link"), dict)
    }
    assert str(report_a) in deep_records
    assert str(report_b) not in deep_records
