from types import SimpleNamespace

import app


def test_activate_notification_deep_link_persists_anchor_and_query_params(monkeypatch):
    fake_st = SimpleNamespace(session_state={}, query_params={})
    monkeypatch.setattr(app, "st", fake_st)
    app._activate_notification_deep_link(
        {
            "page": "Operations",
            "tab": "maintenance",
            "record_id": "55",
            "highlight": True,
            "anchor": "maintenance_editor",
        }
    )
    pending = fake_st.session_state.get("pending_deep_link")
    assert pending is not None
    assert pending["anchor"] == "maintenance_editor"
    assert fake_st.query_params["page"] == "Operations"
    assert fake_st.query_params["tab"] == "maintenance"
    assert fake_st.query_params["id"] == "55"
    assert fake_st.query_params["anchor"] == "maintenance_editor"
