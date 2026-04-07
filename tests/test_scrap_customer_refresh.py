from pathlib import Path
import re


def test_scrap_save_marks_customer_data_changed():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"conn\.commit\(\)\s+_mark_data_changed\(\"customers\"\)\s+if new_name and new_phone:",
        re.MULTILINE,
    )
    assert pattern.search(source), "Scrap save flow must refresh customer caches."


def test_scrap_delete_marks_customer_data_changed():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"if delete:\s+conn\.execute\(\"DELETE FROM customers WHERE customer_id=\?\", \(int\(selected_id\),\)\)\s+conn\.commit\(\)\s+_mark_data_changed\(\"customers\"\)",
        re.MULTILINE,
    )
    assert pattern.search(source), "Scrap delete flow must refresh customer caches."
