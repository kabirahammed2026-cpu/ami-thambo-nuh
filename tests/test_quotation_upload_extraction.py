import io
import zipfile

import app


def _build_docx_with_text(text: str) -> bytes:
    document_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:body><w:p><w:r><w:t>"
        f"{text}"
        "</w:t></w:r></w:p></w:body></w:document>"
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_extract_text_from_txt_upload():
    text, warnings = app._extract_text_from_quotation_bytes(
        b"Quotation Ref Q-001\\nGenerator set", ".txt"
    )
    assert "Quotation Ref Q-001" in text
    assert warnings == []


def test_extract_text_from_docx_upload():
    payload = _build_docx_with_text("Client ACME Quotation")
    text, warnings = app._extract_text_from_quotation_bytes(payload, ".docx")
    assert "Client ACME Quotation" in text
    assert warnings == []


def test_extract_text_from_legacy_doc_upload_warns():
    text, warnings = app._extract_text_from_quotation_bytes(b"legacy-doc", ".doc")
    assert text == ""
    assert any("Legacy .doc parsing" in warning for warning in warnings)
