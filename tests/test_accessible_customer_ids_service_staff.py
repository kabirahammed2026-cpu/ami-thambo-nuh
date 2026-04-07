import pandas as pd

import app


def test_accessible_customer_ids_service_staff_is_unscoped(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_is_service_staff", lambda: True)

    assert app.accessible_customer_ids(None) is None


def test_accessible_customer_ids_sales_staff_only_own_ids(monkeypatch):
    monkeypatch.setattr(app, "current_user_is_admin", lambda: False)
    monkeypatch.setattr(app, "current_user_is_service_staff", lambda: False)
    monkeypatch.setattr(app, "current_user_id", lambda: 9)
    monkeypatch.setattr(
        app,
        "df_query",
        lambda conn, query, params=(): pd.DataFrame({"customer_id": ["1", 2, None, "bad"]}),
    )

    ids = app.accessible_customer_ids(object())

    assert ids == {1, 2}
