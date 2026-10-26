"""FastAPI routes for documents, matching, review, chat, and Alan escalation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

from app.schemas import (
    AlanInvestigation,
    AlanInvestigationRequest,
    CaseDetail,
    CaseSummary,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Dashboard,
    Health,
    PurchaseOrder,
    ReviewRequest,
)
from app.services.cases import CaseNotFound, CaseService, DocumentProcessingError
from app.services.chat import ChatService
from app.services.parsing import sanitize_filename
from app.services.purchase_orders import load_purchase_orders

router = APIRouter()


def _cases(request: Request) -> CaseService:
    return request.app.state.case_service


def _chat(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.get("/health", response_model=Health)
def health(request: Request) -> Health:
    settings = request.app.state.settings
    return Health(
        status="ok",
        version=settings.version,
        model_configured=settings.model_enabled,
        model_name=settings.model_name,
        alan_workflow_configured=settings.alan_workflow_enabled,
        alan_missing=settings.alan_missing,
        demo_mode=True,
    )


@router.get("/dashboard", response_model=Dashboard)
def dashboard(request: Request) -> Dashboard:
    return _cases(request).dashboard()


@router.get("/purchase-orders", response_model=list[PurchaseOrder])
def purchase_orders(request: Request) -> list[PurchaseOrder]:
    return load_purchase_orders(request.app.state.settings)


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(request: Request, limit: int = 200, offset: int = 0) -> list[CaseSummary]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return _cases(request).list_cases(limit=limit, offset=offset)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, request: Request) -> CaseDetail:
    return _cases(request).get_case(case_id)


@router.get("/cases/{case_id}/document")
def get_document(case_id: str, request: Request) -> FileResponse:
    path, media_type = _cases(request).case_document(case_id)
    safe_name = sanitize_filename(path.name)
    return FileResponse(
        path,
        media_type=media_type,
        filename=safe_name,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, max-age=60",
        },
    )


@router.post("/documents", response_model=CaseDetail, status_code=201)
async def upload_document(
    request: Request, file: UploadFile = File(...)
) -> CaseDetail:
    settings = request.app.state.settings
    limit_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit_bytes + 1)
    if len(data) > limit_bytes:
        raise DocumentProcessingError(
            "too_large",
            f"The file is larger than the {settings.max_upload_mb} MB demo limit.",
            413,
        )
    try:
        return _cases(request).create_document(
            data,
            file.filename,
            file.content_type,
            source="upload",
        )
    finally:
        await file.close()


@router.post("/cases/{case_id}/review", response_model=CaseDetail)
def review_case(
    case_id: str, payload: ReviewRequest, request: Request
) -> CaseDetail:
    return _cases(request).review_case(case_id, payload)


@router.get("/cases/{case_id}/messages", response_model=list[ChatMessage])
def list_messages(case_id: str, request: Request) -> list[ChatMessage]:
    return _chat(request).messages(case_id)


@router.post("/cases/{case_id}/chat", response_model=ChatResponse)
def chat(case_id: str, payload: ChatRequest, request: Request) -> ChatResponse:
    return _chat(request).ask(case_id, payload.message)


@router.post(
    "/cases/{case_id}/alan/investigations",
    response_model=AlanInvestigation,
    status_code=202,
)
def start_alan_investigation(
    case_id: str, payload: AlanInvestigationRequest, request: Request
) -> AlanInvestigation:
    service = request.app.state.alan_service
    detail = _cases(request).get_case(case_id)
    question = payload.question.strip() or "Explain what a human should check."
    return service.start(detail, question, _cases(request))


@router.get(
    "/cases/{case_id}/alan/investigations", response_model=list[AlanInvestigation]
)
def list_alan_investigations(
    case_id: str, request: Request
) -> list[AlanInvestigation]:
    _cases(request).get_case(case_id)
    return request.app.state.alan_service.list_for_case(case_id)


@router.get(
    "/alan/investigations/{execution_id}", response_model=AlanInvestigation
)
def poll_alan_investigation(
    execution_id: str, request: Request
) -> AlanInvestigation:
    return request.app.state.alan_service.poll(execution_id)


@router.get("/cases/{case_id}/exists")
def case_exists(case_id: str, request: Request) -> dict[str, bool]:
    try:
        _cases(request).get_case(case_id)
    except CaseNotFound:
        return {"exists": False}
    return {"exists": True}