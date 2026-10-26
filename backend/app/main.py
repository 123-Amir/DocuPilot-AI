"""DocuPilot AI FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import PROJECT_ROOT, Settings, get_settings
from app.db import Store
from app.routes.api import router
from app.services.alan_mcp import AlanIntegrationError
from app.services.cases import CaseNotFound, CaseService, DocumentProcessingError
from app.services.chat import ChatService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("docupilot")


def _error(status_code: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, **extra}},
    )


def create_app(
    settings: Settings | None = None,
    store: Store | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    store = store or Store(settings.db_path)

    case_service = CaseService(settings, store)
    chat_service = ChatService(settings, store, case_service)
    from app.services.alan_mcp import AlanWorkflowService

    alan_service = AlanWorkflowService(settings, store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.auto_seed:
            try:
                created = case_service.seed_if_empty()
                if created:
                    logger.info("dashboard seeded with %s synthetic demo cases", created)
            except Exception:  # never block the API on optional demo data
                logger.exception("demo seeding failed")
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Synthetic invoice-to-PO reconciliation demo. Deterministic matching in "
            "Python; open-model explanations; human review only. Never pays invoices."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.case_service = case_service
    app.state.chat_service = chat_service
    app.state.alan_service = alan_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    @app.exception_handler(DocumentProcessingError)
    async def _document_error(_: Request, exc: DocumentProcessingError) -> JSONResponse:
        return _error(
            exc.status_code,
            exc.code,
            exc.message,
            case_id=exc.case_id,
        )

    @app.exception_handler(CaseNotFound)
    async def _case_not_found(_: Request, __: CaseNotFound) -> JSONResponse:
        return _error(404, "case_not_found", "That case does not exist.")

    @app.exception_handler(AlanIntegrationError)
    async def _alan_error(_: Request, exc: AlanIntegrationError) -> JSONResponse:
        extra = {"missing": exc.missing} if hasattr(exc, "missing") else {}
        return _error(exc.status_code, exc.code, exc.message, **extra)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = first.get("msg", "Invalid request.")
        return _error(
            422,
            "validation_error",
            f"{location}: {message}" if location else message,
        )

    app.include_router(router, prefix="/api")

    dist = PROJECT_ROOT / "frontend" / "dist"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Serve the built React app when frontend/dist exists."""
        index = dist / "index.html"
        if not index.is_file():
            raise HTTPException(
                status_code=404,
                detail="Frontend build not found. Run `npm install && npm run build` "
                "in frontend/, or use the Vite dev server on port 5173.",
            )
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        if full_path:
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(dist.resolve())
            except ValueError:
                candidate = Path("/nonexistent")
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index)

    return app


app = create_app()