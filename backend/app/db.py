"""Small SQLite store for demo cases, review state, and chat transcripts.

The canonical case payload is a JSON document. Indexed columns exist only for
list/dashboard queries, which keeps schema evolution cheap for a hackathon demo.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    vendor_name TEXT,
    invoice_number TEXT,
    total_amount TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_messages_case ON messages(case_id, created_at);

CREATE TABLE IF NOT EXISTS alan_runs (
    execution_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alan_case ON alan_runs(case_id, updated_at DESC);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- cases

    def save_case(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cases (id, created_at, status, source, vendor_name,
                                   invoice_number, total_amount, review_status,
                                   payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    vendor_name=excluded.vendor_name,
                    invoice_number=excluded.invoice_number,
                    total_amount=excluded.total_amount,
                    review_status=excluded.review_status,
                    payload_json=excluded.payload_json
                """,
                (
                    payload["id"],
                    payload["created_at"],
                    payload["status"],
                    payload["source"],
                    payload.get("vendor_name"),
                    payload.get("invoice_number"),
                    str(payload["total_amount"]) if payload.get("total_amount") else None,
                    payload["review"]["status"],
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_cases(self, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM cases ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def count_cases(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM cases").fetchone()
        return int(row["n"])

    def delete_case(self, case_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------- messages

    def add_message(
        self,
        case_id: str,
        role: Literal["user", "assistant"],
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "role": role,
            "content": content,
            "created_at": iso(utcnow()),
            "meta": meta or {},
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (id, case_id, role, content, created_at, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message["id"],
                    case_id,
                    role,
                    content,
                    message["created_at"],
                    json.dumps(message["meta"], ensure_ascii=False, default=str),
                ),
            )
        return message

    def list_messages(self, case_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, case_id, role, content, created_at, meta_json "
                "FROM messages WHERE case_id = ? ORDER BY created_at ASC",
                (case_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["created_at"] = parse_iso(item["created_at"])
            item["meta"] = json.loads(item.pop("meta_json"))
            result.append(item)
        return result

    def count_messages(self, case_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE case_id = ?", (case_id,)
            ).fetchone()
        return int(row["n"])

    # ------------------------------------------------------------- alan runs

    def save_alan_run(self, case_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO alan_runs (execution_id, case_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    payload["execution_id"],
                    case_id,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    iso(utcnow()),
                ),
            )

    def get_alan_run(self, execution_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM alan_runs WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_alan_runs(self, case_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM alan_runs WHERE case_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (case_id, limit),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]