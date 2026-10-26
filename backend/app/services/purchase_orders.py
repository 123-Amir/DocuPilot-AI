"""Load and validate the synthetic purchase-order book."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import Settings
from app.schemas import PurchaseOrder


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime_ns: int) -> tuple[PurchaseOrder, ...]:
    del mtime_ns
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("purchase_orders.json must contain a list.")
    return tuple(PurchaseOrder.model_validate(item) for item in raw)


def load_purchase_orders(settings: Settings) -> list[PurchaseOrder]:
    path = settings.po_file
    return list(_load_cached(str(path), path.stat().st_mtime_ns))