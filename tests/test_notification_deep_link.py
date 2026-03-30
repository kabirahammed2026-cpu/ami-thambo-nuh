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
            "section": "maintenance_editor",
            "field": "status",
            "context": "Maintenance #55",
        }
    )
    pending = fake_st.session_state.get("pending_deep_link")
    assert pending is not None
    assert pending["anchor"] == "maintenance_editor"
    assert pending["section"] == "maintenance_editor"
    assert pending["field"] == "status"
    assert pending["context"] == "Maintenance #55"
    assert fake_st.query_params["page"] == "Operations"
    assert fake_st.query_params["tab"] == "maintenance"
    assert fake_st.query_params["id"] == "55"
    assert fake_st.query_params["anchor"] == "maintenance_editor"
    assert fake_st.query_params["section"] == "maintenance_editor"
    assert fake_st.query_params["field"] == "status"
    assert fake_st.query_params["context"] == "Maintenance #55"


def test_apply_extracted_deep_link_skips_repeat_query_param_writes(monkeypatch):
    fake_st = SimpleNamespace(session_state={}, query_params={})
    monkeypatch.setattr(app, "st", fake_st)
    persist_calls = {"count": 0}

    def fake_persist(payload):
        persist_calls["count"] += 1
        fake_st.query_params["page"] = payload.get("page")

    monkeypatch.setattr(app, "_persist_deep_link_query_params", fake_persist)
    payload = {
        "page": "Operations",
        "tab": "maintenance",
        "record_id": "55",
        "highlight": "1",
        "anchor": "maintenance_editor",
        "section": "",
        "field": "",
        "file": "",
        "context": "",
    }

    app._apply_extracted_deep_link(dict(payload))
    app._apply_extracted_deep_link(dict(payload))

    assert persist_calls["count"] == 1
    assert fake_st.session_state.get("nav_page") == "Operations"
    assert fake_st.session_state.get("_active_deep_link_token")
