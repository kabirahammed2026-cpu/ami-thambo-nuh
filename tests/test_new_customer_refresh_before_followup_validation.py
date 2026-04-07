from pathlib import Path
import re


def test_new_customer_save_marks_customer_data_changed_before_optional_followups():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"conn\.commit\(\)\s+\s*# Bump customer data versions immediately after the base customer save\.[\s\S]*?_mark_data_changed\(\"customers\"\)\s+if cleaned_products:",
        re.MULTILINE,
    )

    assert pattern.search(source), (
        "Create-customer flow should refresh customer data versions immediately after the "
        "base customer save so optional follow-up validation returns do not hide saved customers."
    )
