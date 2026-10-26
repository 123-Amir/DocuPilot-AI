"""Pydantic contracts shared by the API, services, and tests."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["high", "medium", "low", "info"]
CaseStatus = Literal["needs_review", "no_mismatch", "failed"]
ReviewStatus = Literal[
    "pending_review",
    "in_review",
    "reviewed_ok",
    "needs_vendor_contact",
    "rejected",
]
ExtractionMode = Literal["model", "fixture", "unavailable"]


class FieldEvidence(BaseModel):
    field: str
    snippet: str | None = None
    page: int | None = None
    source: Literal["invoice_text", "invoice_image", "po_record", "computed"] = (
        "invoice_text"
    )


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    sku: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    line_total_source: Literal["extracted", "computed"] | None = None
    evidence: FieldEvidence | None = None


class ExtractedInvoice(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    currency: str | None = None
    po_number: str | None = None
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)

    def evidence_for(self, field: str) -> list[FieldEvidence]:
        return [item for item in self.evidence if item.field == field]


class PurchaseOrderLine(BaseModel):
    sku: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class PurchaseOrder(BaseModel):
    po_number: str
    vendor_name: str
    issue_date: date
    currency: str
    total_amount: Decimal
    line_items: list[PurchaseOrderLine]

    def evidence_for(self, field: str, value: str | None = None) -> list[FieldEvidence]:
        return [
            FieldEvidence(
                field=field,
                snippet=value or f"{field} from purchase order {self.po_number}",
                source="po_record",
            )
        ]


class Flag(BaseModel):
    id: str
    code: str
    severity: Severity
    title: str
    field: str | None = None
    invoice_value: str | None = None
    po_value: str | None = None
    delta: str | None = None
    rule: str
    detail: str
    evidence: list[FieldEvidence] = Field(default_factory=list)


class Check(BaseModel):
    name: str
    status: Literal["pass", "fail", "info"]
    detail: str


class MatchResult(BaseModel):
    purchase_order: PurchaseOrder | None = None
    po_match_method: Literal["po_number", "vendor", "none"] = "none"
    flags: list[Flag] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    computed_line_sum: Decimal | None = None
    printed_total: Decimal | None = None
    arithmetic_delta: Decimal | None = None
    vendor_similarity: float | None = None


class Review(BaseModel):
    status: ReviewStatus = "pending_review"
    note: str | None = None
    reviewer: str | None = None
    updated_at: datetime | None = None


class ModelInfo(BaseModel):
    provider: str = "Alan model gateway"
    model: str | None = None
    mode: ExtractionMode = "unavailable"
    elapsed_ms: int | None = None
    note: str | None = None


class CaseSummary(BaseModel):
    id: str
    created_at: datetime
    filename: str
    status: CaseStatus
    source: Literal["demo", "upload"]
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    currency: str | None = None
    total_amount: Decimal | None = None
    po_number: str | None = None
    flag_count: int = 0
    high_flag_count: int = 0
    review_status: ReviewStatus = "pending_review"
    extraction_mode: ExtractionMode = "unavailable"
    error: str | None = None


class CaseDetail(CaseSummary):
    invoice: ExtractedInvoice | None = None
    purchase_order: PurchaseOrder | None = None
    match: MatchResult | None = None
    review: Review = Field(default_factory=Review)
    model: ModelInfo = Field(default_factory=ModelInfo)
    document_url: str | None = None
    chat_message_count: int = 0


class ChatMessage(BaseModel):
    id: str
    case_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    citations: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    source: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    message: ChatMessage
    citations: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    source: str


class ReviewRequest(BaseModel):
    status: ReviewStatus
    note: str | None = Field(default=None, max_length=2000)
    reviewer: str | None = Field(default=None, max_length=120)


class AlanInvestigationRequest(BaseModel):
    question: str = Field(default="Explain what should be checked before this invoice is reviewed.", max_length=2000)


class AlanInvestigation(BaseModel):
    execution_id: str
    case_id: str | None = None
    workflow_id: str
    status: str
    question: str
    output: str | None = None
    error: str | None = None
    started_at: datetime
    updated_at: datetime
    url: str | None = None
    polls: int = 0


class FlagCount(BaseModel):
    code: str
    label: str
    count: int


class DashboardStats(BaseModel):
    total_documents: int
    needs_review: int
    no_mismatch: int
    failed: int
    high_flags: int
    reviewed: int
    model_configured: bool
    alan_workflow_configured: bool


class Dashboard(BaseModel):
    stats: DashboardStats
    flag_counts: list[FlagCount]
    recent: list[CaseSummary]


class Health(BaseModel):
    status: str
    version: str
    model_configured: bool
    model_name: str
    alan_workflow_configured: bool
    alan_missing: list[str]
    demo_mode: bool = True
    warning: str = (
        "Demo only. DocuPilot AI does not approve, schedule, or execute payments."
    )
