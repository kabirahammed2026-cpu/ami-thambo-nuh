from pathlib import Path
import re


def test_new_customer_merge_updates_customer_owner_for_staff_visibility():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"if created_by is not None:\s+existing_owner_row = conn\.execute\(\s+\"SELECT created_by FROM customers WHERE customer_id=\?\",\s+\(cid,\),\s+\)\.fetchone\(\)\s+existing_owner = int_or_none\(existing_owner_row\[0\]\) if existing_owner_row else None\s+if existing_owner != created_by:\s+conn\.execute\(\s+\"UPDATE customers SET created_by=\? WHERE customer_id=\?\",\s+\(created_by, cid\),\s+\)",
        re.MULTILINE,
    )
    assert pattern.search(source), (
        "Merged customer saves must update created_by so staff can still find the customer in scoped pages."
    )
