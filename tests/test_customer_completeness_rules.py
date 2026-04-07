import app


def test_customer_complete_clause_requires_name_and_phone_only():
    clause = app.customer_complete_clause()
    assert "name" in clause
    assert "phone" in clause
    assert "address" not in clause


def test_required_customer_fields_match_completion_rule():
    assert app.REQUIRED_CUSTOMER_FIELDS == {"name": "Name", "phone": "Phone"}
