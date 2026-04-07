from pathlib import Path
import re


def test_new_customer_with_phone_skips_name_only_merge_fallback():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"existing_customer_id = merge_customers_by_phone\(conn, phone_val\)\s+if existing_customer_id is None and not phone_val:\s+# Only fall back to name/company merge when no phone is provided\.\s+# If a phone number exists and does not match, keep the new entry\s+# as a distinct customer so it appears in scoped selectors\.\s+existing_customer_id = _lookup_customer_id_for_merge\(",
        re.MULTILINE,
    )
    assert pattern.search(source), (
        "New customer save must avoid name/company merge fallback when a phone is provided, "
        "so distinct phone entries remain visible."
    )
