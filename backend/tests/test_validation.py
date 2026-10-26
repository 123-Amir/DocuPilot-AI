from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from app.services.parsing import UploadValidationError, validate_and_parse

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def _error_code(callable_) -> str:
    with pytest.raises(UploadValidationError) as excinfo:
        callable_()
    return excinfo.value.code


def test_rejects_unsupported_extension(settings):
    code = _error_code(
        lambda: validate_and_parse(b"hello", "notes.txt", "text/plain", settings)
    )
    assert code == "unsupported_extension"


def test_rejects_disguised_file(settings):
    data = (SAMPLES / "northwind_inv_1042.pdf").read_bytes()
    code = _error_code(
        lambda: validate_and_parse(data, "invoice.png", "image/png", settings)
    )
    assert code == "content_type_mismatch"


def test_rejects_non_document_bytes(settings):
    code = _error_code(
        lambda: validate_and_parse(b"<svg></svg>", "invoice.png", "image/png", settings)
    )
    assert code == "unsupported_type"


def test_rejects_empty_file(settings):
    code = _error_code(lambda: validate_and_parse(b"", "invoice.pdf", "application/pdf", settings))
    assert code == "empty_file"


def test_rejects_corrupt_pdf(settings):
    code = _error_code(
        lambda: validate_and_parse(
            b"%PDF-1.7\nnot really a pdf", "invoice.pdf", "application/pdf", settings
        )
    )
    assert code == "corrupt_pdf"


def test_rejects_oversized_upload(settings):
    tiny_limit = replace(settings, max_upload_mb=1)
    data = b"%PDF-" + b"0" * (1024 * 1024 + 8)
    code = _error_code(
        lambda: validate_and_parse(data, "invoice.pdf", "application/pdf", tiny_limit)
    )
    assert code == "too_large"


def test_rejects_too_many_pages(settings):
    document = pymupdf.open()
    for _ in range(6):
        document.new_page()
    data = document.tobytes()
    document.close()
    code = _error_code(
        lambda: validate_and_parse(data, "invoice.pdf", "application/pdf", settings)
    )
    assert code == "too_many_pages"


def test_accepts_synthetic_png_as_image_mode(settings):
    data = (SAMPLES / "aster_inv_5591.png").read_bytes()
    parsed = validate_and_parse(data, "aster.png", "image/png", settings)
    assert parsed.text_mode == "image"
    assert parsed.page_count == 1
    assert parsed.image_data_urls and parsed.image_data_urls[0].startswith("data:image/jpeg;base64,")
    assert len(parsed.sha256) == 64


def test_accepts_text_pdf_and_extracts_text(settings):
    data = (SAMPLES / "northwind_inv_1042.pdf").read_bytes()
    parsed = validate_and_parse(data, "northwind.pdf", "application/pdf", settings)
    assert parsed.text_mode == "text"
    assert "Northwind Office Supply" in parsed.text
    assert "PO-2026-014" in parsed.text
    assert parsed.image_data_urls == []