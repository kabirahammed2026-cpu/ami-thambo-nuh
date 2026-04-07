import app


def test_customer_scope_filter_service_staff_is_unscoped(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_current_user",
        lambda: {"role": "staff", "staff_classification": "service", "user_id": 12},
    )
    monkeypatch.setattr(app, "current_user_id", lambda: 12)

    clause, params = app.customer_scope_filter("c")

    assert clause == ""
    assert params == ()


def test_customer_scope_filter_sales_staff_is_owned_only(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_current_user",
        lambda: {"role": "staff", "staff_classification": "sales", "user_id": 7},
    )
    monkeypatch.setattr(app, "current_user_id", lambda: 7)

    clause, params = app.customer_scope_filter("c")

    assert clause == "c.created_by = ?"
    assert params == (7,)
