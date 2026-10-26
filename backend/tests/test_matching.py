from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas import ExtractedInvoice, LineItem, PurchaseOrder, PurchaseOrderLine
from app.services.matching import case_status, evaluate, vendor_similarity


def _codes(result) -> set[str]:
    return {flag.code for flag in result.flags}


def test_clean_invoice_matches_without_review_flags(make_demo_case):
    case = make_demo_case("northwind_inv_1042.pdf")
    assert case.status == "no_mismatch"
    assert case.match is not None
    assert _codes(case.match) == set()
    assert case.match.purchase_order is not None
    assert case.match.purchase_order.po_number == "PO-2026-014"
    assert case.match.computed_line_sum == Decimal("1840.00")
    assert all(
        check.status in {"pass", "info"} for check in case.match.checks
    )


def test_amount_discrepancy_has_exact_values_and_evidence(make_demo_case):
    case = make_demo_case("meridian_inv_88213.pdf")
    assert case.status == "needs_review"
    assert case.match is not None
    codes = _codes(case.match)
    assert "total_mismatch" in codes
    assert "line_unit_price_mismatch" in codes
    assert "line_total_mismatch" in codes

    total_flag = next(flag for flag in case.match.flags if flag.code == "total_mismatch")
    assert total_flag.severity == "high"
    assert total_flag.invoice_value == "1,265.00"
    assert total_flag.po_value == "1,240.00"
    assert total_flag.delta == "25.00"
    assert total_flag.evidence
    assert any("TOTAL DUE" in (item.snippet or "") for item in total_flag.evidence)

    unit_flag = next(
        flag for flag in case.match.flags if flag.code == "line_unit_price_mismatch"
    )
    assert unit_flag.invoice_value == "7.25"
    assert unit_flag.po_value == "7.00"
    assert unit_flag.delta == "0.25"
    assert unit_flag.evidence


def test_missing_fields_and_vendor_mismatch(make_demo_case):
    case = make_demo_case("aster_inv_5591.png")
    assert case.status == "needs_review"
    assert case.match is not None
    codes = _codes(case.match)
    assert "vendor_mismatch" in codes
    assert "po_not_found" not in codes

    missing_fields = {
        flag.field for flag in case.match.flags if flag.code == "missing_field"
    }
    assert {"invoice_number", "currency"} <= missing_fields

    vendor_flag = next(
        flag for flag in case.match.flags if flag.code == "vendor_mismatch"
    )
    assert vendor_flag.invoice_value == "Aster Logistik Services"
    assert vendor_flag.po_value == "Aster Logistics GmbH"
    assert vendor_flag.evidence
    assert case.match.vendor_similarity is not None
    assert case.match.vendor_similarity < 0.86


def test_line_arithmetic_and_total_subtotal_mismatch(make_demo_case):
    case = make_demo_case("helio_inv_77120.pdf")
    assert case.match is not None
    codes = _codes(case.match)
    assert "arithmetic_mismatch" in codes
    assert "line_unit_price_mismatch" in codes
    assert "line_total_mismatch" in codes

    arithmetic = next(
        flag for flag in case.match.flags if flag.code == "arithmetic_mismatch"
    )
    assert arithmetic.invoice_value == "2,110.00"
    assert arithmetic.po_value == "2,070.00"
    assert arithmetic.delta == "40.00"
    assert case.match.computed_line_sum == Decimal("2070.00")


def test_tolerance_is_one_cent():
    po = PurchaseOrder(
        po_number="PO-TEST-1",
        vendor_name="Example Supply",
        issue_date=date(2026, 1, 1),
        currency="USD",
        total_amount=Decimal("100.00"),
        line_items=[
            PurchaseOrderLine(
                sku="X-1",
                description="Widget",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
            )
        ],
    )
    base = dict(
        vendor_name="Example Supply",
        invoice_number="INV-1",
        invoice_date=date(2026, 1, 2),
        currency="USD",
        po_number="PO-TEST-1",
        line_items=[
            LineItem(
                description="Widget",
                sku="X-1",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
            )
        ],
    )
    within = evaluate(
        ExtractedInvoice(total_amount=Decimal("100.01"), subtotal=Decimal("100.01"), **base),
        [po],
    )
    assert "total_mismatch" not in _codes(within)

    over = evaluate(
        ExtractedInvoice(total_amount=Decimal("100.02"), subtotal=Decimal("100.02"), **base),
        [po],
    )
    assert "total_mismatch" in _codes(over)
    trip = next(flag for flag in over.flags if flag.code == "total_mismatch")
    assert trip.delta == "0.02"


def test_vendor_normalization_ignores_legal_suffixes():
    assert vendor_similarity("Northwind Office Supply Inc.", "Northwind Office Supply") == 1.0
    assert vendor_similarity("Aster Logistik Services", "Aster Logistics GmbH") < 0.86


def test_case_status_requires_human_review_for_high_or_medium():
    assert case_status([]) == "no_mismatch"
    invoice = ExtractedInvoice(
        vendor_name="Vendor",
        invoice_number="INV-1",
        invoice_date=date(2026, 1, 1),
        currency="USD",
        total_amount=Decimal("10.00"),
        line_items=[
            LineItem(
                description="Thing",
                quantity=Decimal("1"),
                unit_price=Decimal("10.00"),
                line_total=Decimal("10.00"),
            )
        ],
    )
    result = evaluate(invoice, [])
    assert case_status(result.flags) == "needs_review"