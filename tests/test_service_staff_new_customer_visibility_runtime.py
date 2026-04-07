import sqlite3
from pathlib import Path

import app


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "visibility.db"
    monkeypatch.setattr(app, "DB_PATH", str(db_path))
    app._load_customer_group_rows.clear()
    app._count_cached.clear()

    conn = sqlite3.connect(str(db_path))
    app.init_schema(conn)
    conn.execute(
        "INSERT INTO users (user_id, username, pass_hash, role, staff_classification) VALUES (2, 'service_user', 'x', 'staff', 'service')"
    )
    conn.execute(
        "INSERT INTO users (user_id, username, pass_hash, role, staff_classification) VALUES (3, 'sales_user', 'x', 'staff', 'sales')"
    )
    conn.commit()
    monkeypatch.setattr(
        app,
        "get_current_user",
        lambda: {"user_id": 2, "role": "staff", "staff_classification": "service"},
    )
    monkeypatch.setattr(app, "current_user_id", lambda: 2)
    return conn


def _assert_visible_in_downstream_helpers(conn: sqlite3.Connection, customer_id: int):
    clause, params = app.customer_scope_filter("c")
    assert clause == ""
    assert params == ()
    assert app.accessible_customer_ids(conn) is None

    groups, _ = app.build_customer_groups(conn, only_complete=False)
    grouped_ids = {cid for group in groups for cid in group["ids"]}
    assert customer_id in grouped_ids

    options, _, group_map, _ = app.fetch_customer_choices(conn, only_complete=False)
    assert any(customer_id in ids for ids in group_map.values())
    assert any(opt is not None for opt in options)

    operations_rows = conn.execute("SELECT c.customer_id FROM customers c ORDER BY c.customer_id").fetchall()
    assert customer_id in {int(row[0]) for row in operations_rows}

    conn.execute("INSERT INTO products (product_id, name, model) VALUES (1, 'Pump', 'X')")
    conn.execute(
        "INSERT INTO warranties (customer_id, product_id, serial, issue_date, expiry_date, status) VALUES (?, 1, 'S-1', '2026-01-01', '2027-01-01', 'active')",
        (customer_id,),
    )
    conn.commit()
    warranty_scope, warranty_params = app.customer_scope_filter("c")
    scope_sql = f" AND {warranty_scope}" if warranty_scope else ""
    warranty_rows = conn.execute(
        f"""
        SELECT w.warranty_id
        FROM warranties w
        LEFT JOIN customers c ON c.customer_id = w.customer_id
        WHERE COALESCE(w.status, 'active') NOT IN ('deleted', 'completed')
          AND w.customer_id = ?
          {scope_sql}
        """,
        (customer_id, *warranty_params),
    ).fetchall()
    assert warranty_rows

    conn.execute("UPDATE customers SET remarks=? WHERE customer_id=?", (app.LEAD_REMARK_TAG, customer_id))
    conn.commit()
    lead_scope, lead_params = app.customer_scope_filter("c")
    lead_where = f" WHERE {lead_scope}" if lead_scope else ""
    lead_rows = conn.execute(
        f"SELECT customer_id FROM customers c{lead_where}",
        lead_params,
    ).fetchall()
    assert customer_id in {int(row[0]) for row in lead_rows}


def test_service_staff_new_customer_visible_across_downstream_paths(tmp_path, monkeypatch):
    conn = _setup_db(tmp_path, monkeypatch)
    try:
        customer_id, was_merged = app.save_customer_from_create_flow(
            conn,
            name="New Service Customer",
            company_name="",
            phone="01711-000001",
            address="",
            delivery_address="",
            remarks="",
            purchase_date="2026-04-07",
            product_info="",
            delivery_order_code="",
            sales_person="",
            amount_spent=None,
            created_by=2,
        )

        assert was_merged is False
        _assert_visible_in_downstream_helpers(conn, customer_id)
    finally:
        conn.close()


def test_service_staff_create_flow_merge_keeps_customer_visible_and_reowned(tmp_path, monkeypatch):
    conn = _setup_db(tmp_path, monkeypatch)
    try:
        conn.execute(
            "INSERT INTO customers (customer_id, name, phone, created_by, dup_flag) VALUES (10, 'Legacy', '01711-111222', 3, 0)"
        )
        conn.commit()

        customer_id, was_merged = app.save_customer_from_create_flow(
            conn,
            name="Merged Name",
            company_name="",
            phone="01711-111222",
            address="Addr",
            delivery_address="Addr",
            remarks="Updated",
            purchase_date="2026-04-07",
            product_info="Product",
            delivery_order_code="DO-1",
            sales_person="Svc",
            amount_spent=100.0,
            created_by=2,
        )

        assert was_merged is True
        assert customer_id == 10
        owner = conn.execute("SELECT created_by FROM customers WHERE customer_id=?", (customer_id,)).fetchone()
        assert owner and owner[0] == 2
        _assert_visible_in_downstream_helpers(conn, customer_id)
    finally:
        conn.close()
