import pandas as pd

import app


def test_filter_maintenance_records_for_view_returns_only_current_staff_rows(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_id", lambda: 7)
    df = pd.DataFrame(
        [
            {"maintenance_id": 1, "created_by": 7, "description": "mine"},
            {"maintenance_id": 2, "created_by": 8, "description": "other"},
            {"maintenance_id": 3, "created_by": None, "description": "unowned"},
        ]
    )
    filtered = app.filter_maintenance_records_for_view(df)
    assert filtered["maintenance_id"].tolist() == [1]


def test_maintenance_scope_filter_is_strict_for_staff(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_id", lambda: 12)
    clause, params = app.maintenance_scope_filter("m")
    assert clause == "m.created_by = ?"
    assert params == (12,)


def test_filter_maintenance_records_for_view_handles_missing_created_by(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_id", lambda: 12)
    df = pd.DataFrame([{"maintenance_id": 1, "description": "row"}])
    filtered = app.filter_maintenance_records_for_view(df)
    assert filtered.empty


def test_filter_maintenance_records_for_view_handles_non_numeric_created_by(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_id", lambda: 12)
    df = pd.DataFrame(
        [
            {"maintenance_id": 1, "created_by": "abc"},
            {"maintenance_id": 2, "created_by": "12"},
        ]
    )
    filtered = app.filter_maintenance_records_for_view(df)
    assert filtered["maintenance_id"].tolist() == [2]
