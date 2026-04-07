from pathlib import Path
import re


def test_new_customer_maintenance_insert_sets_created_by_for_staff_visibility():
    source = Path("app.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"INSERT INTO maintenance_records \(\s+do_number,\s+customer_id,\s+maintenance_date,\s+maintenance_start_date,\s+maintenance_end_date,\s+description,\s+status,\s+remarks,\s+maintenance_product_info,\s+total_amount,\s+payment_status,\s+payment_receipt_path,\s+updated_at,\s+created_by\s+\) VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, datetime\('now'\), \?\)",
        re.MULTILINE,
    )

    assert pattern.search(source), (
        "Create-customer maintenance saves must include created_by so scoped staff pages can find the new record."
    )
