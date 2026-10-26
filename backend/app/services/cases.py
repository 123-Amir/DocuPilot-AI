"""Case lifecycle: upload -> parse -> extract -> match -> review -> chat."""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db import Store, iso, utcnow
from app.money import money_str, plain_money_str
from app.schemas import (
    CaseDetail,
    CaseStatus,
    CaseSummary,
    Dashboard,
    DashboardStats,
    ExtractedInvoice,
    Flag,
    FlagCount,
    MatchResult,
    ModelInfo,
    Review,
    ReviewRequest,
)
from app.services.extraction import (
    ExtractionError,
    ExtractionResult,
    extract_invoice,
    load_manifest,
)
from app.services.matching import FLAG_LABELS, case_status, evaluate
from app.services.parsing import (
    ParsedDocument,
    UploadValidationError,
    validate_and_parse,
)
from app.services.provider import AlanModelClient
from app.services.purchase_orders import load_purchase_orders

logger = logging.getLogger(__name__)


class CaseNotFound(Exception):
    pass


class DocumentProcessingError(Exception):
    def __init__(self, code: str, message: str, status_code: int, case_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.case_id = case_id


def _new_case_id() -> str:
    return f"CASE-{uuid.uuid4().hex[:10].upper()}"


class CaseService:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store
        self.client = AlanModelClient(settings)
        self.purchase_orders = load_purchase_orders(settings)

    # -------------------------------------------------------------- creation

    def create_document(
        self,
        data: bytes,
        filename: str | None,
        content_type: str | None,
        *,
        source: str = "upload",
        force_fixture: bool = False,
    ) -> CaseDetail:
        try:
            parsed = validate_and_parse(
                data, filename, content_type, self.settings
            )
        except UploadValidationError as exc:
            raise DocumentProcessingError(exc.code, exc.message, exc.status_code) from exc

        case_id = _new_case_id()
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path = self.settings.upload_dir / f"{case_id}{parsed.extension}"
        stored_path.write_bytes(data)

        try:
            extraction = extract_invoice(
                parsed, self.settings, self.client, force_fixture=force_fixture
            )
        except ExtractionError as exc:
            self._save_failed(case_id, parsed, source, stored_path, exc.code, exc.message)
            raise DocumentProcessingError(
                exc.code, exc.message, exc.status_code, case_id=case_id
            ) from exc

        match = evaluate(extraction.invoice, self.purchase_orders)
        status = case_status(match.flags)
        payload = self._build_payload(
            case_id=case_id,
            parsed=parsed,
            source=source,
            stored_path=stored_path,
            extraction=extraction,
            match=match,
            status=status,
        )
        self.store.save_case(payload)
        logger.info(
            "case created id=%s source=%s flags=%s status=%s",
            case_id,
            source,
            len(match.flags),
            status,
        )
        return self.get_case(case_id)

    def _build_payload(
        self,
        *,
        case_id: str,
        parsed: ParsedDocument,
        source: str,
        stored_path: Path,
        extraction: ExtractionResult,
        match: MatchResult,
        status: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        invoice = extraction.invoice
        high_count = sum(1 for flag in match.flags if flag.severity == "high")
        created_at = iso(utcnow())
        return {
            "id": case_id,
            "created_at": created_at,
            "updated_at": created_at,
            "filename": parsed.filename,
            "source": source,
            "status": status,
            "document_path": str(stored_path),
            "document_mime": parsed.mime_type,
            "document_sha256": parsed.sha256,
            "document_size": parsed.size_bytes,
            "vendor_name": invoice.vendor_name,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat()
            if invoice.invoice_date
            else None,
            "currency": invoice.currency,
            "total_amount": plain_money_str(invoice.total_amount),
            "po_number": match.purchase_order.po_number
            if match.purchase_order
            else invoice.po_number,
            "flag_count": len(match.flags),
            "high_flag_count": high_count,
            "invoice": invoice.model_dump(mode="json"),
            "purchase_order": match.purchase_order.model_dump(mode="json")
            if match.purchase_order
            else None,
            "match": match.model_dump(mode="json"),
            "review": Review().model_dump(mode="json"),
            "model": extraction.info.model_dump(mode="json"),
            "extraction_raw": extraction.raw,
            "error": error,
        }

    def _save_failed(
        self,
        case_id: str,
        parsed: ParsedDocument,
        source: str,
        stored_path: Path,
        code: str,
        message: str,
    ) -> None:
        now = iso(utcnow())
        payload = {
            "id": case_id,
            "created_at": now,
            "updated_at": now,
            "filename": parsed.filename,
            "source": source,
            "status": "failed",
            "document_path": str(stored_path),
            "document_mime": parsed.mime_type,
            "document_sha256": parsed.sha256,
            "document_size": parsed.size_bytes,
            "vendor_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "currency": None,
            "total_amount": None,
            "po_number": None,
            "flag_count": 0,
            "high_flag_count": 0,
            "invoice": None,
            "purchase_order": None,
            "match": None,
            "review": Review().model_dump(mode="json"),
            "model": ModelInfo(
                provider="Alan model gateway",
                model=self.settings.model_name,
                mode="unavailable",
                note=message,
            ).model_dump(mode="json"),
            "extraction_raw": None,
            "error": f"{code}: {message}",
        }
        self.store.save_case(payload)

    # ----------------------------------------------------------------- read

    def get_case(self, case_id: str) -> CaseDetail:
        payload = self.store.get_case(case_id)
        if payload is None:
            raise CaseNotFound(case_id)
        return self._detail(payload)

    def list_cases(self, limit: int = 200, offset: int = 0) -> list[CaseSummary]:
        return [self._summary(item) for item in self.store.list_cases(limit, offset)]

    def dashboard(self) -> Dashboard:
        payloads = self.store.list_cases(limit=1000)
        statuses = Counter(item.get("status") for item in payloads)
        reviewed_states = {"reviewed_ok", "needs_vendor_contact", "rejected"}
        reviewed = sum(
            1
            for item in payloads
            if item.get("review", {}).get("status") in reviewed_states
        )
        flag_counts: Counter[str] = Counter()
        for item in payloads:
            match = item.get("match") or {}
            for flag in match.get("flags", []):
                flag_counts[flag.get("code", "unknown")] += 1
        ordered_flags = [
            FlagCount(code=code, label=FLAG_LABELS.get(code, code), count=count)
            for code, count in flag_counts.most_common()
        ]
        return Dashboard(
            stats=DashboardStats(
                total_documents=len(payloads),
                needs_review=statuses.get("needs_review", 0),
                no_mismatch=statuses.get("no_mismatch", 0),
                failed=statuses.get("failed", 0),
                high_flags=sum(int(item.get("high_flag_count") or 0) for item in payloads),
                reviewed=reviewed,
                model_configured=self.settings.model_enabled,
                alan_workflow_configured=self.settings.alan_workflow_enabled,
            ),
            flag_counts=ordered_flags,
            recent=[self._summary(item) for item in payloads[:8]],
        )

    def _summary(self, payload: dict[str, Any]) -> CaseSummary:
        return CaseSummary.model_validate(
            {
                "id": payload["id"],
                "created_at": payload["created_at"],
                "filename": payload["filename"],
                "status": payload.get("status", "failed"),
                "source": payload.get("source", "upload"),
                "vendor_name": payload.get("vendor_name"),
                "invoice_number": payload.get("invoice_number"),
                "invoice_date": payload.get("invoice_date"),
                "currency": payload.get("currency"),
                "total_amount": payload.get("total_amount"),
                "po_number": payload.get("po_number"),
                "flag_count": payload.get("flag_count", 0),
                "high_flag_count": payload.get("high_flag_count", 0),
                "review_status": payload.get("review", {}).get(
                    "status", "pending_review"
                ),
                "extraction_mode": (payload.get("model") or {}).get(
                    "mode", "unavailable"
                ),
                "error": payload.get("error"),
            }
        )

    def _detail(self, payload: dict[str, Any]) -> CaseDetail:
        summary = self._summary(payload)
        review = Review.model_validate(payload.get("review") or {})
        model = ModelInfo.model_validate(payload.get("model") or {})
        document_path = self.document_path(payload)
        return CaseDetail(
            **summary.model_dump(),
            invoice=ExtractedInvoice.model_validate(payload["invoice"])
            if payload.get("invoice")
            else None,
            purchase_order=payload.get("purchase_order"),
            match=MatchResult.model_validate(payload["match"])
            if payload.get("match")
            else None,
            review=review,
            model=model,
            document_url=(
                f"/api/cases/{payload['id']}/document" if document_path else None
            ),
            chat_message_count=self.store.count_messages(payload["id"]),
        )

    def document_path(self, payload: dict[str, Any]) -> Path | None:
        raw = payload.get("document_path")
        if not raw:
            return None
        try:
            path = Path(raw).resolve()
            root = self.settings.upload_dir.resolve()
            path.relative_to(root)
        except (OSError, ValueError):
            return None
        return path if path.is_file() else None

    def case_document(self, case_id: str) -> tuple[Path, str]:
        payload = self.store.get_case(case_id)
        if payload is None:
            raise CaseNotFound(case_id)
        path = self.document_path(payload)
        if path is None:
            raise CaseNotFound(case_id)
        return path, payload.get("document_mime") or "application/octet-stream"

    # --------------------------------------------------------------- review

    def review_case(self, case_id: str, request: ReviewRequest) -> CaseDetail:
        payload = self.store.get_case(case_id)
        if payload is None:
            raise CaseNotFound(case_id)
        review = Review(
            status=request.status,
            note=request.note,
            reviewer=request.reviewer,
            updated_at=utcnow().astimezone(timezone.utc),
        )
        payload["review"] = review.model_dump(mode="json")
        payload["updated_at"] = iso(utcnow())
        self.store.save_case(payload)
        logger.info("review updated case=%s status=%s", case_id, request.status)
        return self.get_case(case_id)

    # ----------------------------------------------------------------- seed

    def seed_if_empty(self) -> int:
        if not self.settings.auto_seed or self.store.count_cases() > 0:
            return 0
        manifest = load_manifest(self.settings)
        created = 0
        for entry in manifest.get("invoices", []):
            path = self.settings.samples_dir / str(entry.get("filename"))
            if not path.is_file():
                continue
            try:
                self.create_document(
                    path.read_bytes(),
                    path.name,
                    "application/pdf" if path.suffix.lower() == ".pdf" else "image/png",
                    source="demo",
                    force_fixture=True,
                )
                created += 1
            except Exception as exc:  # seeding must never stop the API
                logger.warning("demo seed failed for %s: %s", path.name, exc)
        if created:
            logger.info("seeded %s demo cases", created)
        return created

    # --------------------------------------------------------------- helpers

    def flags_for(self, detail: CaseDetail) -> list[Flag]:
        return detail.match.flags if detail.match else []

    def facts_for_prompt(self, detail: CaseDetail) -> dict[str, Any]:
        match = detail.match
        invoice = detail.invoice
        return {
            "case_id": detail.id,
            "status": detail.status,
            "review_status": detail.review.status,
            "invoice": {
                "vendor_name": invoice.vendor_name if invoice else None,
                "invoice_number": invoice.invoice_number if invoice else None,
                "invoice_date": detail.invoice_date.isoformat()
                if detail.invoice_date
                else None,
                "currency": detail.currency,
                "total_amount": money_str(detail.total_amount),
                "po_number": invoice.po_number if invoice else None,
            }
            if invoice
            else None,
            "purchase_order": {
                "po_number": detail.purchase_order.po_number,
                "vendor_name": detail.purchase_order.vendor_name,
                "issue_date": detail.purchase_order.issue_date.isoformat(),
                "currency": detail.purchase_order.currency,
                "total_amount": money_str(detail.purchase_order.total_amount),
            }
            if detail.purchase_order
            else None,
            "deterministic_arithmetic": {
                "computed_line_sum": money_str(match.computed_line_sum)
                if match
                else None,
                "printed_total": money_str(match.printed_total) if match else None,
                "delta": money_str(match.arithmetic_delta) if match else None,
            },
            "flags": [
                {
                    "id": flag.id,
                    "code": flag.code,
                    "severity": flag.severity,
                    "title": flag.title,
                    "field": flag.field,
                    "invoice_value": flag.invoice_value,
                    "po_value": flag.po_value,
                    "delta": flag.delta,
                    "rule": flag.rule,
                    "detail": flag.detail,
                    "evidence": [
                        {
                            "field": evidence.field,
                            "snippet": evidence.snippet,
                            "page": evidence.page,
                            "source": evidence.source,
                        }
                        for evidence in flag.evidence
                    ],
                }
                for flag in (match.flags if match else [])
            ],
            "checks": [
                {"name": check.name, "status": check.status, "detail": check.detail}
                for check in (match.checks if match else [])
            ],
            "model": {
                "provider": detail.model.provider,
                "model": detail.model.model,
                "mode": detail.model.mode,
            },
        }

    def record_message(
        self, case_id: str, role: str, content: str, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.store.add_message(case_id, role, content, meta)  # type: ignore[arg-type]

    def compact_case_brief(self, detail: CaseDetail) -> str:
        facts = self.facts_for_prompt(detail)
        return json.dumps(facts, ensure_ascii=False, separators=(",", ":"))