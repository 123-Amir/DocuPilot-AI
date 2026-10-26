"""Generate synthetic invoice PDFs/PNGs and their deterministic fixture manifest.

Usage (from the backend/ directory):
    python scripts/generate_samples.py

Everything here is invented for the demo. The documents contain no real company,
person, address, tax ID, or bank account.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = BACKEND_ROOT / "samples"
PO_FILE = BACKEND_ROOT / "app" / "data" / "purchase_orders.json"

NAVY = (0.06, 0.13, 0.25)
BLUE = (0.15, 0.39, 0.92)
GRAY = (0.42, 0.45, 0.5)
LIGHT = (0.95, 0.96, 0.98)
WHITE = (1, 1, 1)


def money(value: str | Decimal) -> str:
    return f"{Decimal(str(value)):,.2f}"


def text_right(
    page: fitz.Page,
    x_right: float,
    y: float,
    text: str,
    *,
    fontsize: float,
    fontname: str,
    color: tuple[float, float, float],
) -> None:
    width = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    page.insert_text((x_right - width, y), text, fontsize=fontsize, fontname=fontname, color=color)


def render_invoice(spec: dict) -> fitz.Document:
    document = fitz.open()
    page = document.new_page(width=595, height=842)

    # Watermark first so it sits behind the content.
    page.insert_text(
        (210, 500),
        "DEMO",
        fontsize=90,
        fontname="hebo",
        color=(0.93, 0.94, 0.97),
    )
    page.draw_rect(fitz.Rect(0, 0, 595, 6), color=None, fill=BLUE)

    # Vendor block.
    page.insert_text((50, 62), spec["vendor"], fontsize=16, fontname="hebo", color=NAVY)
    address_lines = [
        "1400 Harbor Way, Suite 220",
        "Portland, OR 97209",
        "billing@demo-supplier.example",
        "Tax ID 00-0000000 (synthetic)",
    ]
    y = 82
    for line in address_lines:
        page.insert_text((50, y), line, fontsize=8.5, fontname="helv", color=GRAY)
        y += 12

    page.insert_text((410, 66), "INVOICE", fontsize=24, fontname="hebo", color=NAVY)

    meta: list[tuple[str, str]] = []
    if spec.get("number"):
        meta.append(("Invoice No.", spec["number"]))
    meta.append(("Invoice Date", spec["date"]))
    meta.append(("PO Number", spec["po"]))
    if spec.get("currency"):
        meta.append(("Currency", spec["currency"]))
    meta_y = 92
    for label, value in meta:
        page.insert_text((410, meta_y), label, fontsize=8, fontname="helv", color=GRAY)
        text_right(page, 545, meta_y, value, fontsize=9, fontname="hebo", color=NAVY)
        meta_y += 15

    page.draw_line(fitz.Point(50, 150), fitz.Point(545, 150), color=(0.85, 0.87, 0.9), width=1)

    page.insert_text((50, 176), "BILL TO", fontsize=8, fontname="hebo", color=GRAY)
    page.insert_text((50, 192), "Contoso Demo Labs", fontsize=11, fontname="hebo", color=NAVY)
    for offset, line in enumerate(
        ["Accounts Payable", "500 Example Avenue", "Seattle, WA 98101"]
    ):
        page.insert_text((50, 207 + offset * 12), line, fontsize=8.5, fontname="helv", color=GRAY)

    page.insert_text((410, 176), "SHIP TO", fontsize=8, fontname="hebo", color=GRAY)
    for offset, line in enumerate(["Contoso Demo Labs", "Receiving Dock B", "Seattle, WA 98101"]):
        page.insert_text((410, 192 + offset * 12), line, fontsize=8.5, fontname="helv", color=GRAY)

    # Table header.
    table_top = 262
    page.draw_rect(fitz.Rect(50, table_top, 545, table_top + 22), color=None, fill=LIGHT)
    headers = [
        ("DESCRIPTION", 56, 0),
        ("SKU", 310, 0),
        ("QTY", 402, 2),
        ("UNIT", 468, 2),
        ("AMOUNT", 539, 2),
    ]
    for text, x, align in headers:
        if align == 2:
            text_right(page, x, table_top + 14, text, fontsize=7.5, fontname="hebo", color=GRAY)
        else:
            page.insert_text(
                (x, table_top + 14),
                text,
                fontsize=7.5,
                fontname="hebo",
                color=GRAY,
            )

    y = table_top + 40
    for line in spec["lines"]:
        description = line["description"]
        words = description.split()
        wrapped: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if fitz.get_text_length(candidate, fontname="helv", fontsize=9) > 230:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        if current:
            wrapped.append(current)

        page.insert_text((56, y), wrapped[0], fontsize=9, fontname="helv", color=NAVY)
        for extra in wrapped[1:3]:
            y += 11
            page.insert_text((56, y), extra, fontsize=9, fontname="helv", color=NAVY)
        page.insert_text((310, y - (len(wrapped[1:3]) * 11)), line["sku"], fontsize=8.5, fontname="helv", color=GRAY)
        text_right(page, 402, y - (len(wrapped[1:3]) * 11), line["qty"], fontsize=9, fontname="helv", color=NAVY)
        text_right(page, 468, y - (len(wrapped[1:3]) * 11), money(line["unit"]), fontsize=9, fontname="helv", color=NAVY)
        text_right(page, 539, y - (len(wrapped[1:3]) * 11), money(line["total"]), fontsize=9, fontname="helv", color=NAVY)
        y += 22
        page.draw_line(
            fitz.Point(50, y - 12),
            fitz.Point(545, y - 12),
            color=(0.9, 0.92, 0.95),
            width=0.6,
        )

    # Totals.
    totals_y = max(y + 18, 520)
    page.draw_line(fitz.Point(350, totals_y - 10), fitz.Point(545, totals_y - 10), color=(0.82, 0.85, 0.9), width=1)
    totals = [
        ("Subtotal", spec["subtotal"]),
        ("Tax (0%)", spec["tax"]),
    ]
    row_y = totals_y + 4
    for label, value in totals:
        page.insert_text((356, row_y), label, fontsize=9, fontname="helv", color=GRAY)
        text_right(page, 545, row_y, money(value), fontsize=9, fontname="helv", color=NAVY)
        row_y += 17

    page.draw_rect(fitz.Rect(350, row_y - 2, 545, row_y + 24), color=None, fill=(0.93, 0.96, 1))
    page.insert_text((356, row_y + 15), "TOTAL DUE", fontsize=10, fontname="hebo", color=NAVY)
    symbol = symbol_for(spec.get("currency"))
    total_value = money(spec["total_display"])
    total_text = f"{symbol}{total_value}" if symbol else total_value
    text_right(page, 545, row_y + 15, total_text, fontsize=12, fontname="hebo", color=BLUE)

    # Footer.
    page.draw_line(fitz.Point(50, 770), fitz.Point(545, 770), color=(0.85, 0.87, 0.9), width=1)
    page.insert_text(
        (50, 786),
        "SYNTHETIC DEMO DOCUMENT - NOT A REAL INVOICE. NO PAYMENT OBLIGATION.",
        fontsize=8,
        fontname="hebo",
        color=(0.7, 0.2, 0.2),
    )
    page.insert_text(
        (50, 798),
        "Generated for DocuPilot AI. Every vendor, address, PO, and amount is invented.",
        fontsize=7.5,
        fontname="helv",
        color=GRAY,
    )
    text_right(page, 545, 798, "Page 1 of 1", fontsize=7.5, fontname="helv", color=GRAY)
    return document


def symbol_for(currency: str | None) -> str:
    return {"USD": "$", "EUR": "â‚¬", "GBP": "Â£"}.get(currency or "", "")


def expected_payload(spec: dict) -> dict:
    symbol = symbol_for(spec.get("currency"))
    evidence = {
        "vendor_name": {"snippet": spec["vendor"], "page": 1},
        "invoice_date": {"snippet": f"Invoice Date {spec['date']}", "page": 1},
        "po_number": {"snippet": f"PO Number {spec['po']}", "page": 1},
    }
    if spec.get("number"):
        evidence["invoice_number"] = {
            "snippet": f"Invoice No. {spec['number']}",
            "page": 1,
        }
    if spec.get("currency"):
        evidence["currency"] = {
            "snippet": f"Currency {spec['currency']}",
            "page": 1,
        }
    evidence["subtotal"] = {"snippet": f"Subtotal {money(spec['subtotal'])}", "page": 1}
    evidence["tax_amount"] = {"snippet": f"Tax (0%) {money(spec['tax'])}", "page": 1}
    evidence["total_amount"] = {
        "snippet": f"TOTAL DUE {symbol}{money(spec['total_display'])}".strip(),
        "page": 1,
    }

    lines = []
    for line in spec["lines"]:
        lines.append(
            {
                "description": line["description"],
                "sku": line["sku"],
                "quantity": line["qty"],
                "unit_price": money(line["unit"]),
                "line_total": money(line["total"]),
                "evidence": {
                    "snippet": (
                        f"{line['sku']} {line['description']} {line['qty']} x "
                        f"{money(line['unit'])} = {money(line['total'])}"
                    ),
                    "page": 1,
                },
            }
        )

    return {
        "vendor_name": spec["vendor"],
        "invoice_number": spec.get("number"),
        "invoice_date": spec["date"],
        "currency": spec.get("currency"),
        "po_number": spec["po"],
        "subtotal": money(spec["subtotal"]),
        "tax_amount": money(spec["tax"]),
        "total_amount": money(spec["total_display"]),
        "line_items": lines,
        "evidence": evidence,
    }


def invoice_specs() -> list[dict]:
    return [
        {
            "filename": "northwind_inv_1042.pdf",
            "scenario": "Clean match: Northwind invoice agrees with PO-2026-014.",
            "vendor": "Northwind Office Supply",
            "number": "NW-INV-1042",
            "date": "2026-10-06",
            "currency": "USD",
            "po": "PO-2026-014",
            "lines": [
                {
                    "description": "A4 Copy Paper 80gsm",
                    "sku": "NW-1001",
                    "qty": "40",
                    "unit": "6.50",
                    "total": "260.00",
                },
                {
                    "description": "Ergonomic Task Chair",
                    "sku": "NW-2044",
                    "qty": "4",
                    "unit": "320.00",
                    "total": "1280.00",
                },
                {
                    "description": "Laser Printer Toner (Black)",
                    "sku": "NW-3300",
                    "qty": "10",
                    "unit": "30.00",
                    "total": "300.00",
                },
            ],
            "subtotal": "1840.00",
            "tax": "0.00",
            "total_display": "1840.00",
        },
        {
            "filename": "meridian_inv_88213.pdf",
            "scenario": (
                "Amount discrepancy: Meridian bills paper at 7.25 instead of the "
                "PO rate of 7.00, raising the total by 25.00."
            ),
            "vendor": "Meridian Paper Co",
            "number": "MP-88213",
            "date": "2026-10-07",
            "currency": "USD",
            "po": "PO-2026-021",
            "lines": [
                {
                    "description": "Recycled Letter Paper",
                    "sku": "MP-880",
                    "qty": "100",
                    "unit": "7.25",
                    "total": "725.00",
                },
                {
                    "description": "Archival Document Boxes",
                    "sku": "MP-915",
                    "qty": "30",
                    "unit": "18.00",
                    "total": "540.00",
                },
            ],
            "subtotal": "1265.00",
            "tax": "0.00",
            "total_display": "1265.00",
        },
        {
            "filename": "aster_inv_5591.png",
            "scenario": (
                "Vendor and missing-field scenario: 'Aster Logistik Services' does not "
                "match PO vendor 'Aster Logistics GmbH', and the invoice has no invoice "
                "number or currency."
            ),
            "vendor": "Aster Logistik Services",
            "number": None,
            "date": "2026-10-09",
            "currency": None,
            "po": "PO-2026-033",
            "lines": [
                {
                    "description": "Pallet Freight (Domestic)",
                    "sku": "AL-10",
                    "qty": "6",
                    "unit": "120.00",
                    "total": "720.00",
                },
                {
                    "description": "Tail-lift Handling",
                    "sku": "AL-22",
                    "qty": "8",
                    "unit": "30.00",
                    "total": "240.00",
                },
            ],
            "subtotal": "960.00",
            "tax": "0.00",
            "total_display": "960.00",
        },
        {
            "filename": "helio_inv_77120.pdf",
            "scenario": (
                "Line and arithmetic scenario: Helio bills first-aid kits at 85.00 vs the "
                "PO's 95.00, and the printed subtotal (2,110.00) does not equal the "
                "extracted line totals (2,070.00)."
            ),
            "vendor": "Helio Industrial Supply",
            "number": "HI-77120",
            "date": "2026-10-11",
            "currency": "USD",
            "po": "PO-2026-047",
            "lines": [
                {
                    "description": "Safety Gloves (Large)",
                    "sku": "HI-510",
                    "qty": "20",
                    "unit": "24.50",
                    "total": "490.00",
                },
                {
                    "description": "Nitrile Gloves (Medium)",
                    "sku": "HI-620",
                    "qty": "25",
                    "unit": "28.00",
                    "total": "700.00",
                },
                {
                    "description": "Hearing Protection",
                    "sku": "HI-740",
                    "qty": "30",
                    "unit": "18.00",
                    "total": "540.00",
                },
                {
                    "description": "First Aid Kits",
                    "sku": "HI-880",
                    "qty": "4",
                    "unit": "85.00",
                    "total": "340.00",
                },
            ],
            "subtotal": "2110.00",  # intentionally not equal to line sum (2070.00)
            "tax": "0.00",
            "total_display": "2110.00",
        },
    ]


def validate_purchase_orders() -> int:
    orders = json.loads(PO_FILE.read_text(encoding="utf-8"))
    for order in orders:
        line_sum = sum(Decimal(str(line["line_total"])) for line in order["line_items"])
        assert line_sum == Decimal(str(order["total_amount"])), (
            f"{order['po_number']} lines sum to {line_sum}, "
            f"total says {order['total_amount']}"
        )
    return len(orders)


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for stale in SAMPLES_DIR.glob("*.pdf"):
        stale.unlink()
    for stale in SAMPLES_DIR.glob("*.png"):
        stale.unlink()

    po_count = validate_purchase_orders()
    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Synthetic demo documents generated by scripts/generate_samples.py. "
            "Not real invoices."
        ),
        "purchase_orders_validated": po_count,
        "invoices": [],
    }

    for spec in invoice_specs():
        document = render_invoice(spec)
        target = SAMPLES_DIR / spec["filename"]
        if target.suffix.lower() == ".pdf":
            document.save(target)
        else:
            pixmap = document[0].get_pixmap(dpi=170, alpha=False)
            pixmap.save(target)
        document.close()

        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest["invoices"].append(
            {
                "filename": spec["filename"],
                "sha256": digest,
                "scenario": spec["scenario"],
                "expected": expected_payload(spec),
            }
        )
        print(f"wrote {target.name} ({target.stat().st_size:,} bytes)")

    (SAMPLES_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote manifest.json with {len(manifest['invoices'])} invoices")


if __name__ == "__main__":
    main()



