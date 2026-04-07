from pathlib import Path
import re


def test_new_customer_merge_shows_explicit_feedback_message():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"was_merged_customer = existing_customer_id is not None[\s\S]+if was_merged_customer:\s+st\.session_state\[\"new_customer_feedback\"\] = \(\s+\"info\",\s+\([\s\S]*Matched existing customer record",
        re.MULTILINE,
    )
    assert pattern.search(source), (
        "When a new-customer save merges into an existing record, the UI should explicitly "
        "inform the user to avoid the perception that data disappeared."
    )
