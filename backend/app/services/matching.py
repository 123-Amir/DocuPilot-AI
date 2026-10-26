"""Deterministic invoice-to-purchase-order matching.

This module is deliberately free of model calls. Every financial comparison,
line-item match, and arithmetic check happens here with Decimal values so the
demo never depends on an LLM for money math.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from app.money import CENT, ZERO, money_str, plain_money_str, quantize
from app.schemas import (
    Check,
    ExtractedInvoice,
    FieldEvidence,
    Flag,
    MatchResult,
    PurchaseOrder,
    PurchaseOrderLine,
    Severity,
)

AMOUNT_TOLERANCE = Decimal("0.01")
VENDOR_MATCH_THRESHOLD = 0.86

_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "plc",
    "pte",
    "pty",
    "sa",
    "bv",
    "ag",
    "srl",
    "kg",
    "oy",
    "ab",
}
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_SPACE_RE = re.compile(r"\s+")

_SEVERITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _squash(value: str) -> str:
    return _SPACE_RE.sub(" ", _PUNCT_RE.sub(" ", value.lower())).strip()


def normalize_vendor(name: str | None) -> str:
    if not name:
        return ""
    tokens = [token for token in _squash(name.replace("&", " and ")).split(" ") if token]
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def vendor_similarity(left: str | None, right: str | None) -> float:
    a = normalize_vendor(left)
    b = normalize_vendor(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return round(SequenceMatcher(None, a, b).ratio(), 4)


def normalize_sku(sku: str | None) -> str:
    if not sku:
        return ""
    return re.sub(r"[^a-z0-9]", "", sku.lower())


def normalize_description(description: str | None) -> str:
    return _squash(description or "")


def _money(value: Decimal | None) -> str | None:
    return money_str(value) if value is not None else None


def _qty(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _invoice_evidence(
    invoice: ExtractedInvoice,
    field: str,
    fallback: str | None = None,
) -> list[FieldEvidence]:
    found = invoice.evidence_for(field)
    if found:
        return found
    return [
        FieldEvidence(
            field=field,
            snippet=fallback
            or "No verbatim snippet was captured for this field; value comes from the structured extraction.",
            source="computed",
        )
    ]


def _new_flag(
    *,
    code: str,
    severity: Severity,
    title: str,
    rule: str,
    detail: str,
    field: str | None = None,
    invoice_value: str | None = None,
    po_value: str | None = None,
    delta: str | None = None,
    evidence: list[FieldEvidence] | None = None,
) -> Flag:
    return Flag(
        id="",
        code=code,
        severity=severity,
        title=title,
        field=field,
        invoice_value=invoice_value,
        po_value=po_value,
        delta=delta,
        rule=rule,
        detail=detail,
        evidence=evidence or [],
    )


def find_purchase_order(
    invoice: ExtractedInvoice, orders: list[PurchaseOrder]
) -> tuple[PurchaseOrder | None, str]:
    """Resolve a PO deterministically: exact PO number first, then vendor."""
    if invoice.po_number:
        wanted = normalize_sku(invoice.po_number)
        for order in orders:
            if normalize_sku(order.po_number) == wanted:
                return order, "po_number"
        return None, "none"

    if not invoice.vendor_name:
        return None, "none"

    ranked = sorted(
        (
            (vendor_similarity(invoice.vendor_name, order.vendor_name), order)
            for order in orders
        ),
        key=lambda item: (-item[0], item[1].po_number),
    )
    if ranked and ranked[0][0] >= VENDOR_MATCH_THRESHOLD:
        return ranked[0][1], "vendor"
    return None, "none"


def computed_line_sum(invoice: ExtractedInvoice) -> Decimal | None:
    if not invoice.line_items:
        return None
    total = ZERO
    for item in invoice.line_items:
        value = item.line_total
        if value is None and item.quantity is not None and item.unit_price is not None:
            value = quantize(item.quantity * item.unit_price)
        if value is None:
            return None
        total += value
    return quantize(total)


def _line_key(sku: str | None, description: str | None) -> str:
    normalized_sku = normalize_sku(sku)
    if normalized_sku:
        return f"sku:{normalized_sku}"
    return f"desc:{normalize_description(description)}"


def _pair_lines(
    invoice: ExtractedInvoice, po: PurchaseOrder
) -> tuple[
    list[tuple[int, int]],
    list[tuple[int, Decimal | None]],
    list[tuple[int, PurchaseOrderLine]],
]:
    """Pair invoice lines to PO lines by SKU, then normalized description."""
    invoice_index: dict[str, list[int]] = {}
    for idx, item in enumerate(invoice.line_items):
        invoice_index.setdefault(_line_key(item.sku, item.description), []).append(idx)

    paired: list[tuple[int, int]] = []
    used_invoice: set[int] = set()
    for po_idx, po_line in enumerate(po.line_items):
        key = _line_key(po_line.sku, po_line.description)
        candidates = invoice_index.get(key, [])
        for candidate in candidates:
            if candidate not in used_invoice:
                paired.append((candidate, po_idx))
                used_invoice.add(candidate)
                break

    unmatched_invoice = [
        (idx, item.line_total)
        for idx, item in enumerate(invoice.line_items)
        if idx not in used_invoice
    ]
    used_po = {pair[1] for pair in paired}
    unmatched_po = [
        (idx, line) for idx, line in enumerate(po.line_items) if idx not in used_po
    ]
    return paired, unmatched_invoice, unmatched_po


def evaluate(
    invoice: ExtractedInvoice,
    orders: list[PurchaseOrder],
    *,
    today: date | None = None,
) -> MatchResult:
    """Compare an extracted invoice to the synthetic PO book."""
    today = today or date.today()
    po, method = find_purchase_order(invoice, orders)
    flags: list[Flag] = []
    checks: list[Check] = []

    # ------------------------------------------------------- required fields
    required: list[tuple[str, str, Severity]] = [
        ("vendor_name", "Vendor name", "high"),
        ("invoice_number", "Invoice number", "medium"),
        ("invoice_date", "Invoice date", "medium"),
        ("currency", "Currency", "high"),
        ("total_amount", "Invoice total", "high"),
    ]
    for field, label, severity in required:
        value = getattr(invoice, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            flags.append(
                _new_flag(
                    code="missing_field",
                    severity=severity,
                    title=f"Missing {label.lower()}",
                    field=field,
                    rule="Required field is empty after extraction.",
                    detail=(
                        f"{label} is required for a three-way match but was not found "
                        "in the invoice. A human must read the source document."
                    ),
                    invoice_value=None,
                    po_value="required",
                    evidence=[
                        FieldEvidence(
                            field=field,
                            snippet="Field not present in the extracted document.",
                            source="invoice_text",
                        )
                    ],
                )
            )

    if not invoice.line_items:
        flags.append(
            _new_flag(
                code="missing_field",
                severity="high",
                title="Missing line items",
                field="line_items",
                rule="At least one invoice line item is required.",
                detail=(
                    "No line items were extracted. Amount comparison is limited to the "
                    "invoice total, so a reviewer must inspect the document."
                ),
                invoice_value=None,
                po_value="required",
                evidence=_invoice_evidence(invoice, "line_items", "No line-item table detected."),
            )
        )

    if invoice.invoice_date and invoice.invoice_date > today:
        flags.append(
            _new_flag(
                code="invoice_date_future",
                severity="medium",
                title="Invoice date is in the future",
                field="invoice_date",
                rule="invoice_date must be on or before the processing date.",
                detail=(
                    f"Invoice date {invoice.invoice_date.isoformat()} is later than "
                    f"today ({today.isoformat()})."
                ),
                invoice_value=invoice.invoice_date.isoformat(),
                po_value=today.isoformat(),
                evidence=_invoice_evidence(invoice, "invoice_date"),
            )
        )

    # ------------------------------------------------------------- PO lookup
    if po is None:
        requested = invoice.po_number or "(no PO number on invoice)"
        flags.append(
            _new_flag(
                code="po_not_found",
                severity="high",
                title="No purchase order matched",
                field="po_number",
                rule="Exact PO number, then normalized vendor at >= 0.86 similarity.",
                detail=(
                    f"No purchase order matched {requested}. The invoice cannot be "
                    "compared until a PO is identified."
                ),
                invoice_value=invoice.po_number,
                po_value=None,
                evidence=_invoice_evidence(invoice, "po_number"),
            )
        )
        checks.append(
            Check(
                name="Purchase order matched",
                status="fail",
                detail="No PO matched by number or vendor.",
            )
        )
    else:
        checks.append(
            Check(
                name="Purchase order matched",
                status="pass",
                detail=(
                    f"{po.po_number} matched by "
                    f"{'the PO number printed on the invoice' if method == 'po_number' else 'normalized vendor name'}."
                ),
            )
        )
        if method == "vendor":
            flags.append(
                _new_flag(
                    code="po_matched_by_vendor",
                    severity="info",
                    title="PO inferred from vendor",
                    field="po_number",
                    rule="PO selected because the invoice has no PO number and vendor similarity >= 0.86.",
                    detail=(
                        f"Invoice has no usable PO number. {po.po_number} was selected "
                        f"from vendor '{po.vendor_name}'. Confirm this is the intended order."
                    ),
                    invoice_value=invoice.po_number,
                    po_value=po.po_number,
                    evidence=_invoice_evidence(invoice, "po_number"),
                )
            )

    similarity: float | None = None
    if po is not None:
        # ------------------------------------------------------------ vendor
        if invoice.vendor_name:
            similarity = vendor_similarity(invoice.vendor_name, po.vendor_name)
            if similarity < VENDOR_MATCH_THRESHOLD:
                flags.append(
                    _new_flag(
                        code="vendor_mismatch",
                        severity="high",
                        title="Vendor does not match the purchase order",
                        field="vendor_name",
                        rule="Normalized vendor similarity must be >= 0.86.",
                        detail=(
                            f"Invoice vendor '{invoice.vendor_name}' does not match PO "
                            f"vendor '{po.vendor_name}' (similarity {similarity:.2f}). "
                            "This can indicate the wrong supplier or a fraudulent invoice."
                        ),
                        invoice_value=invoice.vendor_name,
                        po_value=po.vendor_name,
                        evidence=_invoice_evidence(invoice, "vendor_name")
                        + po.evidence_for("vendor_name", po.vendor_name),
                    )
                )
                checks.append(
                    Check(
                        name="Vendor identity",
                        status="fail",
                        detail=f"Similarity {similarity:.2f} is below 0.86.",
                    )
                )
            else:
                checks.append(
                    Check(
                        name="Vendor identity",
                        status="pass",
                        detail=f"Vendor similarity {similarity:.2f} meets the 0.86 threshold.",
                    )
                )
        else:
            checks.append(
                Check(
                    name="Vendor identity",
                    status="info",
                    detail="Cannot compare vendor because the invoice field is missing.",
                )
            )

        # ---------------------------------------------------------- currency
        if invoice.currency and po.currency:
            if invoice.currency != po.currency:
                flags.append(
                    _new_flag(
                        code="currency_mismatch",
                        severity="high",
                        title="Currency differs from the purchase order",
                        field="currency",
                        rule="Invoice currency must equal PO currency; no FX conversion is applied.",
                        detail=(
                            f"Invoice is in {invoice.currency} but the PO is in "
                            f"{po.currency}. DocuPilot does not convert currencies, so "
                            "the totals are not comparable."
                        ),
                        invoice_value=invoice.currency,
                        po_value=po.currency,
                        evidence=_invoice_evidence(invoice, "currency")
                        + po.evidence_for("currency", po.currency),
                    )
                )
                checks.append(
                    Check(
                        name="Currency",
                        status="fail",
                        detail=f"{invoice.currency} vs {po.currency}.",
                    )
                )
            else:
                checks.append(
                    Check(
                        name="Currency",
                        status="pass",
                        detail=f"Both documents use {po.currency}.",
                    )
                )
        else:
            checks.append(
                Check(
                    name="Currency",
                    status="info",
                    detail="Cannot compare currency because the invoice field is missing.",
                )
            )

        # ------------------------------------------------------------- total
        if invoice.total_amount is not None:
            delta = quantize(invoice.total_amount - po.total_amount)
            percent = (
                quantize((delta / po.total_amount) * Decimal("100"))
                if po.total_amount != 0
                else None
            )
            if abs(delta) > AMOUNT_TOLERANCE:
                percent_text = f" ({percent:+.2f}% of PO total)" if percent is not None else ""
                flags.append(
                    _new_flag(
                        code="total_mismatch",
                        severity="high",
                        title="Invoice total differs from the purchase order",
                        field="total_amount",
                        rule="Absolute difference greater than 0.01 triggers a mismatch.",
                        detail=(
                            f"Invoice total {_money(invoice.total_amount)} minus PO total "
                            f"{_money(po.total_amount)} = {_money(delta)}{percent_text}. "
                            "Calculated in Python with Decimal arithmetic."
                        ),
                        invoice_value=_money(invoice.total_amount),
                        po_value=_money(po.total_amount),
                        delta=_money(delta),
                        evidence=_invoice_evidence(invoice, "total_amount")
                        + po.evidence_for("total_amount", _money(po.total_amount)),
                    )
                )
                checks.append(
                    Check(
                        name="Invoice total",
                        status="fail",
                        detail=f"Difference {_money(delta)} exceeds the 0.01 tolerance.",
                    )
                )
            else:
                checks.append(
                    Check(
                        name="Invoice total",
                        status="pass",
                        detail=f"Difference {_money(delta)} is within 0.01.",
                    )
                )
        else:
            checks.append(
                Check(
                    name="Invoice total",
                    status="info",
                    detail="Cannot compare totals because the invoice total is missing.",
                )
            )

        # -------------------------------------------------------------- date
        if invoice.invoice_date and invoice.invoice_date < po.issue_date:
            flags.append(
                _new_flag(
                    code="invoice_predates_po",
                    severity="low",
                    title="Invoice is dated before the purchase order",
                    field="invoice_date",
                    rule="invoice_date must not precede po.issue_date.",
                    detail=(
                        f"Invoice date {invoice.invoice_date.isoformat()} is before "
                        f"PO {po.po_number} issue date {po.issue_date.isoformat()}."
                    ),
                    invoice_value=invoice.invoice_date.isoformat(),
                    po_value=po.issue_date.isoformat(),
                    evidence=_invoice_evidence(invoice, "invoice_date")
                    + po.evidence_for("issue_date", po.issue_date.isoformat()),
                )
            )

        # --------------------------------------------------------- line items
        paired, unmatched_invoice, unmatched_po = _pair_lines(invoice, po)
        line_flag_count = len(flags)
        for invoice_idx, po_idx in paired:
            item = invoice.line_items[invoice_idx]
            po_line = po.line_items[po_idx]
            label = f"Invoice line {invoice_idx + 1} ('{item.description}')"
            evidence = (item.evidence and [item.evidence] or []) or _invoice_evidence(
                invoice, f"line_items[{invoice_idx}]", item.description
            )
            evidence = evidence + po.evidence_for(
                f"line_items[{po_idx}]",
                f"{po_line.description}: {_qty(po_line.quantity)} x {_money(po_line.unit_price)} = {_money(po_line.line_total)}",
            )

            if item.quantity is not None and quantize(item.quantity) != quantize(
                po_line.quantity
            ):
                flags.append(
                    _new_flag(
                        code="line_quantity_mismatch",
                        severity="medium",
                        title="Line-item quantity differs",
                        field=f"line_items[{invoice_idx}].quantity",
                        rule="Quantity must equal the PO quantity.",
                        detail=(
                            f"{label} has quantity {_qty(item.quantity)}; PO line "
                            f"'{po_line.description}' has {_qty(po_line.quantity)}."
                        ),
                        invoice_value=_qty(item.quantity),
                        po_value=_qty(po_line.quantity),
                        delta=_qty(quantize(item.quantity - po_line.quantity)),
                        evidence=evidence,
                    )
                )

            if item.unit_price is not None:
                unit_delta = quantize(item.unit_price - po_line.unit_price)
                if abs(unit_delta) > AMOUNT_TOLERANCE:
                    flags.append(
                        _new_flag(
                            code="line_unit_price_mismatch",
                            severity="high",
                            title="Line-item unit price differs",
                            field=f"line_items[{invoice_idx}].unit_price",
                            rule="Unit price must equal the PO unit price.",
                            detail=(
                                f"{label} bills {_money(item.unit_price)} per unit; the PO "
                                f"agreed {_money(po_line.unit_price)}. Difference "
                                f"{_money(unit_delta)} per unit."
                            ),
                            invoice_value=_money(item.unit_price),
                            po_value=_money(po_line.unit_price),
                            delta=_money(unit_delta),
                            evidence=evidence,
                        )
                    )

            compare_total = item.line_total
            if compare_total is not None:
                total_delta = quantize(compare_total - po_line.line_total)
                if abs(total_delta) > AMOUNT_TOLERANCE:
                    flags.append(
                        _new_flag(
                            code="line_total_mismatch",
                            severity="high",
                            title="Line-item total differs",
                            field=f"line_items[{invoice_idx}].line_total",
                            rule="Line total must equal the PO line total.",
                            detail=(
                                f"{label} totals {_money(compare_total)}; the PO line "
                                f"totals {_money(po_line.line_total)}. Difference "
                                f"{_money(total_delta)}."
                            ),
                            invoice_value=_money(compare_total),
                            po_value=_money(po_line.line_total),
                            delta=_money(total_delta),
                            evidence=evidence,
                        )
                    )

            if (
                item.quantity is not None
                and item.unit_price is not None
                and item.line_total is not None
            ):
                expected = quantize(item.quantity * item.unit_price)
                arithmetic_delta = quantize(item.line_total - expected)
                if abs(arithmetic_delta) > AMOUNT_TOLERANCE:
                    flags.append(
                        _new_flag(
                            code="line_arithmetic_mismatch",
                            severity="medium",
                            title="Line arithmetic does not add up",
                            field=f"line_items[{invoice_idx}].line_total",
                            rule="quantity * unit_price must equal line_total.",
                            detail=(
                                f"{label} prints {_qty(item.quantity)} x "
                                f"{_money(item.unit_price)} = {_money(item.line_total)}, "
                                f"but Python computes {_money(expected)}. Delta "
                                f"{_money(arithmetic_delta)}."
                            ),
                            invoice_value=_money(item.line_total),
                            po_value=_money(expected),
                            delta=_money(arithmetic_delta),
                            evidence=evidence,
                        )
                    )

        for invoice_idx, line_total in unmatched_invoice:
            item = invoice.line_items[invoice_idx]
            flags.append(
                _new_flag(
                    code="line_not_on_po",
                    severity="medium",
                    title="Invoice line is not on the purchase order",
                    field=f"line_items[{invoice_idx}]",
                    rule="Every invoice line must match a PO line by SKU or description.",
                    detail=(
                        f"Invoice line '{item.description}'"
                        + (f" ({_money(line_total)})" if line_total is not None else "")
                        + " has no counterpart on the purchase order."
                    ),
                    invoice_value=item.description,
                    po_value=None,
                    evidence=(item.evidence and [item.evidence] or [])
                    or _invoice_evidence(invoice, f"line_items[{invoice_idx}]", item.description),
                )
            )

        for po_idx, po_line in unmatched_po:
            flags.append(
                _new_flag(
                    code="line_missing_from_invoice",
                    severity="low",
                    title="PO line is not billed on the invoice",
                    field=f"po.line_items[{po_idx}]",
                    rule="Every PO line should appear on the invoice unless cancelled.",
                    detail=(
                        f"PO line '{po_line.description}' for "
                        f"{_money(po_line.line_total)} is not present on the invoice. "
                        "This may be a partial shipment; confirm before reviewing."
                    ),
                    invoice_value=None,
                    po_value=_money(po_line.line_total),
                    evidence=po.evidence_for(
                        f"line_items[{po_idx}]", po_line.description
                    ),
                )
            )

        if len(flags) == line_flag_count:
            checks.append(
                Check(
                    name="Line items",
                    status="pass",
                    detail=(
                        f"All {len(paired)} matched lines agree on quantity, unit price, "
                        "and line total."
                    ),
                )
            )
        else:
            checks.append(
                Check(
                    name="Line items",
                    status="fail",
                    detail=(
                        f"{len(flags) - line_flag_count} line-item issue(s) found across "
                        f"{len(invoice.line_items)} invoice line(s)."
                    ),
                )
            )

    # ------------------------------------------------------------ arithmetic
    line_sum = computed_line_sum(invoice)
    arithmetic_delta = None
    arithmetic_target = (
        invoice.subtotal if invoice.subtotal is not None else invoice.total_amount
    )
    target_label = "printed subtotal" if invoice.subtotal is not None else "printed total"
    if (
        line_sum is not None
        and arithmetic_target is not None
        and abs(line_sum - arithmetic_target) > AMOUNT_TOLERANCE
    ):
        arithmetic_delta = quantize(arithmetic_target - line_sum)
        flags.append(
            _new_flag(
                code="arithmetic_mismatch",
                severity="high",
                title="Invoice lines do not sum to the printed subtotal",
                field="subtotal" if invoice.subtotal is not None else "total_amount",
                rule="sum(line_total) must equal subtotal (or total when no subtotal is printed) within 0.01.",
                detail=(
                    f"Python summed the extracted line totals to {_money(line_sum)}, but "
                    f"the invoice prints {_money(arithmetic_target)} as the {target_label}. "
                    f"Difference {_money(arithmetic_delta)}. Tax or freight may explain it, "
                    "but the invoice must show that explicitly."
                ),
                invoice_value=_money(arithmetic_target),
                po_value=_money(line_sum),
                delta=_money(arithmetic_delta),
                evidence=_invoice_evidence(
                    invoice, "subtotal" if invoice.subtotal is not None else "total_amount"
                ),
            )
        )
        checks.append(
            Check(
                name="Invoice arithmetic",
                status="fail",
                detail=(
                    f"Line sum {_money(line_sum)} differs from {target_label} "
                    f"{_money(arithmetic_target)}."
                ),
            )
        )
    elif line_sum is not None and arithmetic_target is not None:
        checks.append(
            Check(
                name="Invoice arithmetic",
                status="pass",
                detail=f"Line sum {_money(line_sum)} equals the {target_label}.",
            )
        )
    else:
        checks.append(
            Check(
                name="Invoice arithmetic",
                status="info",
                detail="Not enough line totals to verify the printed total.",
            )
        )

    if (
        invoice.subtotal is not None
        and invoice.tax_amount is not None
        and invoice.total_amount is not None
    ):
        expected_total = quantize(invoice.subtotal + invoice.tax_amount)
        if abs(expected_total - invoice.total_amount) > AMOUNT_TOLERANCE:
            flags.append(
                _new_flag(
                    code="totals_inconsistent",
                    severity="medium",
                    title="Subtotal plus tax does not equal the total",
                    field="total_amount",
                    rule="subtotal + tax_amount must equal total_amount within 0.01.",
                    detail=(
                        f"Subtotal {_money(invoice.subtotal)} + tax "
                        f"{_money(invoice.tax_amount)} = {_money(expected_total)}, but the "
                        f"invoice prints {_money(invoice.total_amount)}."
                    ),
                    invoice_value=_money(invoice.total_amount),
                    po_value=_money(expected_total),
                    delta=_money(quantize(invoice.total_amount - expected_total)),
                    evidence=_invoice_evidence(invoice, "total_amount"),
                )
            )

    # ------------------------------------------------------------ finalize
    flags.sort(key=lambda item: (_SEVERITY_ORDER[item.severity], item.code, item.title))
    for index, flag in enumerate(flags, start=1):
        flag.id = f"FLAG-{index:03d}"

    return MatchResult(
        purchase_order=po,
        po_match_method=method,  # type: ignore[arg-type]
        flags=flags,
        checks=checks,
        computed_line_sum=line_sum,
        printed_total=invoice.total_amount,
        arithmetic_delta=arithmetic_delta,
        vendor_similarity=similarity,
    )


def case_status(flags: list[Flag]) -> str:
    """A case needs human review when any high or medium flag exists."""
    if any(flag.severity in {"high", "medium"} for flag in flags):
        return "needs_review"
    return "no_mismatch"


@dataclass(frozen=True)
class FlagDefinition:
    code: str
    label: str


FLAG_LABELS: dict[str, str] = {
    "missing_field": "Missing fields",
    "po_not_found": "PO not found",
    "po_matched_by_vendor": "PO inferred by vendor",
    "vendor_mismatch": "Vendor mismatch",
    "currency_mismatch": "Currency mismatch",
    "total_mismatch": "Total mismatch",
    "invoice_predates_po": "Invoice predates PO",
    "invoice_date_future": "Future invoice date",
    "line_quantity_mismatch": "Quantity mismatch",
    "line_unit_price_mismatch": "Unit price mismatch",
    "line_total_mismatch": "Line total mismatch",
    "line_arithmetic_mismatch": "Line arithmetic error",
    "line_not_on_po": "Line not on PO",
    "line_missing_from_invoice": "PO line not invoiced",
    "arithmetic_mismatch": "Totals do not add up",
    "totals_inconsistent": "Subtotal/tax mismatch",
}

assert CENT > ZERO  # keep imported constants meaningful for reviewers