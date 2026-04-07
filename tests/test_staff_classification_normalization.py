import sqlite3

import app


def test_normalize_staff_classification_handles_variants():
    assert app.normalize_staff_classification("Service Staff") == "service"
    assert app.normalize_staff_classification("sales_team") == "sales"
    assert app.normalize_staff_classification(None) == "service"


def test_current_user_staff_classification_uses_normalizer(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_current_user",
        lambda: {"role": "staff", "staff_classification": "Service Staff"},
    )

    assert app.current_user_staff_classification() == "service"
    assert app.current_user_is_service_staff() is True


def test_schema_migration_normalizes_legacy_staff_classification_values(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT, role TEXT, staff_classification TEXT)"
    )
    conn.execute(
        "INSERT INTO users (username, pass_hash, role, staff_classification) VALUES (?, ?, ?, ?)",
        ("svc", "x", "staff", "Service Team"),
    )
    conn.execute(
        "INSERT INTO users (username, pass_hash, role, staff_classification) VALUES (?, ?, ?, ?)",
        ("sales", "x", "staff", "sales_rep"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(app, "DB_PATH", db_path)
    migrated = sqlite3.connect(db_path)
    app.init_schema(migrated)
    migrated.close()

    verify = sqlite3.connect(db_path)
    rows = verify.execute(
        "SELECT username, staff_classification FROM users ORDER BY username"
    ).fetchall()
    verify.close()

    assert rows == [("sales", "sales"), ("svc", "service")]
