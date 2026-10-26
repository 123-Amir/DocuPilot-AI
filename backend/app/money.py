"""Decimal money helpers.

All financial arithmetic in DocuPilot AI goes through Decimal. Floats are only
used at the HTTP/model boundary and are immediately converted or rejected.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

_NUMBER_RE = re.compile(r"-?\(?\d[\d.,\s]*\)?")
_CURRENCY_ALIASES = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "₹": "INR",
    "INR": "INR",
    "¥": "JPY",
    "JPY": "JPY",
    "CAD": "CAD",
    "AUD": "AUD",
    "SGD": "SGD",
}


def quantize(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_money(value: object) -> Decimal | None:
    """Parse a printed money value without ever using float arithmetic.

    Handles ``1,287.50``, ``1.287,50``, ``$ 42.00``, ``(12.50)`` and ``-12.50``.
    Returns None when the value is empty or has no digits.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return quantize(value)
    if isinstance(value, (int,)):
        return quantize(Decimal(value))

    text = str(value).strip()
    if not text:
        return None

    negative = (text.startswith("(") and text.endswith(")")) or text.lstrip().startswith(
        "-"
    )
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    token = match.group(0).strip().strip("()")
    token = token.replace(" ", "").replace("\u00a0", "")
    if token.startswith("-") or token.startswith("−"):
        negative = True
    token = token.replace("−", "-").lstrip("-")
    if not token:
        return None

    has_dot = "." in token
    has_comma = "," in token
    normalized: str
    if has_dot and has_comma:
        if token.rfind(",") > token.rfind("."):
            # European: 1.287,50
            normalized = token.replace(".", "").replace(",", ".")
        else:
            normalized = token.replace(",", "")
    elif has_comma:
        head, _, tail = token.rpartition(",")
        if len(tail) == 2 and head:
            normalized = head.replace(",", "") + "." + tail
        else:
            normalized = token.replace(",", "")
    else:
        normalized = token

    normalized = re.sub(r"[^0-9.]", "", normalized)
    if not normalized or normalized == ".":
        return None
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    if negative:
        number = -number
    return quantize(number)


def parse_quantity(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    numeric = re.sub(r"[^0-9.\-]", "", text)
    if not numeric or numeric in {"-", "."}:
        return None
    try:
        return Decimal(numeric)
    except InvalidOperation:
        return None


def normalize_currency(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[upper]
    for symbol, code in _CURRENCY_ALIASES.items():
        if symbol in raw:
            return code
    if re.fullmatch(r"[A-Z]{3}", upper):
        return upper
    return upper[:8]


def money_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{quantize(value):,.2f}"


def plain_money_str(value: Decimal | None) -> str | None:
    """Machine-friendly money string, e.g. ``1287.50``."""
    if value is None:
        return None
    return f"{quantize(value):.2f}"