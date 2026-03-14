import datetime as dt

import app


def test_parse_display_date_prefers_iso_and_preserves_day_month():
    parsed = app._parse_display_date("2026-03-04")
    assert parsed is not None
    assert parsed.date() == dt.date(2026, 3, 4)


def test_parse_display_date_accepts_local_day_first_formats_consistently():
    expected = dt.date(2026, 3, 4)
    for value in ("04-03-2026", "04.03.2026", "04/03/2026"):
        parsed = app._parse_display_date(value)
        assert parsed is not None
        assert parsed.date() == expected


def test_parse_display_date_handles_datetime_text_without_shifting_date():
    parsed = app._parse_display_date("2026-03-04 14:30:00")
    assert parsed is not None
    assert parsed.date() == dt.date(2026, 3, 4)


def test_format_follow_up_date_is_stable_across_supported_inputs():
    assert app.format_follow_up_date("2026-03-04") == "04.03.2026"
    assert app.format_follow_up_date("04-03-2026") == "04.03.2026"
    assert app.format_follow_up_date("04/03/2026") == "04.03.2026"


def test_format_period_range_uses_consistent_parsing_for_start_and_end():
    label = app.format_period_range("04/03/2026", "06/03/2026")
    assert label == "04-03-2026 → 06-03-2026"
