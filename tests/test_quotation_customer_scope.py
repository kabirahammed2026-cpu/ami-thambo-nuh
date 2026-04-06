import sqlite3

import app


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            company_name TEXT,
            phone TEXT,
            address TEXT,
            delivery_address TEXT,
            remarks TEXT,
            created_by INTEGER,
            dup_flag INTEGER DEFAULT 0
        )
        """
    )
    return conn


def test_manual_quotation_upsert_ignores_inaccessible_customer(monkeypatch):
    conn = _make_conn()
    conn.execute(
        """
        INSERT INTO customers (name, company_name, phone, address, delivery_address, remarks, created_by, dup_flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        ("Legacy Customer", "Legacy Co", "01711-000000", "Old", "Old", None, 99),
    )
    conn.commit()

    monkeypatch.setattr(app, "customer_scope_filter", lambda alias="": ("created_by = ?", (7,)))
    monkeypatch.setattr(app, "_mark_data_changed", lambda *keys: None)
    monkeypatch.setattr(app, "merge_customers_by_phone", lambda _conn, _phone: None)

    customer_id = app._upsert_customer_from_manual_quotation(
        conn,
        name="New Customer",
        company="New Co",
        phone="01711-000000",
        address="New address",
        district="Dhaka",
        created_by=7,
    )

    assert isinstance(customer_id, int)
    rows = conn.execute(
        "SELECT customer_id, name, company_name, created_by FROM customers ORDER BY customer_id ASC"
    ).fetchall()
    assert len(rows) == 2
    assert rows[-1][0] == customer_id
    assert rows[-1][1] == "New Customer"
    assert rows[-1][2] == "New Co"
    assert rows[-1][3] == 7


def test_manual_quotation_upsert_updates_accessible_customer(monkeypatch):
    conn = _make_conn()
    conn.execute(
        """
        INSERT INTO customers (name, company_name, phone, address, delivery_address, remarks, created_by, dup_flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        ("", "", "01711-123456", "", "", None, 7),
    )
    conn.commit()

    monkeypatch.setattr(app, "customer_scope_filter", lambda alias="": ("created_by = ?", (7,)))
    monkeypatch.setattr(app, "_mark_data_changed", lambda *keys: None)
    monkeypatch.setattr(app, "merge_customers_by_phone", lambda _conn, _phone: None)

    customer_id = app._upsert_customer_from_manual_quotation(
        conn,
        name="Visible Customer",
        company="Visible Co",
        phone="01711-123456",
        address="Address",
        district="Dhaka",
        created_by=7,
    )

    rows = conn.execute(
        "SELECT customer_id, name, company_name FROM customers ORDER BY customer_id ASC"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == customer_id
    assert rows[0][1] == "Visible Customer"
    assert rows[0][2] == "Visible Co"
