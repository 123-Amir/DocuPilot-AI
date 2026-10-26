from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.money import normalize_currency, parse_money
from app.services.extraction import (
    extract_json_object,
    normalize_raw_invoice,
    parse_invoice_date,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1,287.50", Decimal("1287.50")),
        ("1.287,50 EUR", Decimal("1287.50")),
        ("(12.50)", Decimal("-12.50")),
        ("-12.50", Decimal("-12.50")),
        ("USD 42", Decimal("42.00")),
        ("", None),
        ("no amount", None),
    ],
)
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-06", date(2026, 10, 6)),
        ("06/10/2026", date(2026, 10, 6)),
        ("10/06/2026", date(2026, 6, 10)),
        ("6 Oct 2026", date(2026, 10, 6)),
        ("not a date", None),
    ],
)
def test_parse_invoice_date(raw, expected):
    assert parse_invoice_date(raw) == expected


def test_parse_invoice_date_handles_unambiguous_day():
    assert parse_invoice_date("25/12/2026") == date(2026, 12, 25)


def test_normalize_currency():
    assert normalize_currency("$") == "USD"
    assert normalize_currency("eur") == "EUR"
    assert normalize_currency("Â£") == "GBP"
    assert normalize_currency(None) is None


def test_extract_json_object_handles_fences_and_chatter():
    raw = 'Here is the result:\n```json\n{"vendor_name": "Acme"}\n```\nThanks.'
    assert extract_json_object(raw) == {"vendor_name": "Acme"}


def test_normalize_computes_missing_line_total():
    invoice = normalize_raw_invoice(
        {
            "vendor_name": "Acme Supply",
            "invoice_number": "A-1",
            "invoice_date": "2026-10-01",
            "currency": "USD",
            "line_items": [
                {
                    "description": "Bolt",
                    "quantity": "2",
                    "unit_price": "3.50",
                }
            ],
            "total_amount": "7.00",
        }
    )
    assert invoice.line_items[0].line_total == Decimal("7.00")
    assert invoice.line_items[0].line_total_source == "computed"
    assert invoice.total_amount == Decimal("7.00")


def test_normalize_empty_payload_is_rejected():
    with pytest.raises(ValueError):
        normalize_raw_invoice({"vendor_name": None, "line_items": []})


def test_aster_fixture_has_missing_fields():
    import json
    from pathlib import Path

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "samples" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    entry = next(
        item for item in manifest["invoices"] if item["filename"] == "aster_inv_5591.png"
    )
    invoice = normalize_raw_invoice(entry["expected"], page_count=1)
    assert invoice.invoice_number is None
    assert invoice.currency is None
    assert invoice.vendor_name == "Aster Logistik Services"
    assert len(invoice.line_items) == 2
