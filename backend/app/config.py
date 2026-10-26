"""Runtime configuration.

Every credential is read from the server environment. Nothing here is sent to
the browser; the frontend only sees boolean capability flags from /api/health.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load a local .env if present. Process environment always wins because
# override=False; this keeps CI and tests in control of their own values.
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(BACKEND_ROOT / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "DocuPilot AI"
    version: str = "0.1.0"

    var_dir: Path = PROJECT_ROOT / "var"
    upload_dir: Path = PROJECT_ROOT / "var" / "uploads"
    db_path: Path = PROJECT_ROOT / "var" / "docupilot.sqlite3"
    samples_dir: Path = BACKEND_ROOT / "samples"
    po_file: Path = BACKEND_ROOT / "app" / "data" / "purchase_orders.json"

    max_upload_mb: int = 10
    max_pdf_pages: int = 5
    max_image_pixels: int = 25_000_000

    # Alan model gateway (OpenAI-compatible, hackathon-provided credits).
    model_base_url: str = "https://api.tryalan.ai/public/harness/v1"
    model_api_key: str = ""
    model_name: str = "qwen/qwen3.8-27b"
    model_fallbacks: tuple[str, ...] = ()
    model_timeout_seconds: float = 90.0
    model_max_tokens: int = 2500
    model_conversation_id: str = ""
    disable_model: bool = False

    # Alan MCP is the product integration surface for workflow escalation.
    alan_mcp_url: str = "https://api.tryalan.ai/mcp"
    alan_mcp_token: str = ""
    alan_conversation_id: str = ""
    alan_workflow_id: str = ""
    alan_timeout_seconds: int = 300
    alan_poll_seconds: float = 3.0

    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    auto_seed: bool = True

    # Derived, filled by __post_init__ via the factory below.
    model_headers: dict[str, str] = field(default_factory=dict)

    @property
    def model_enabled(self) -> bool:
        return bool(self.model_api_key) and not self.disable_model

    @property
    def alan_workflow_enabled(self) -> bool:
        return bool(
            self.alan_mcp_url
            and self.alan_mcp_token
            and self.alan_conversation_id
            and self.alan_workflow_id
        )

    @property
    def alan_missing(self) -> list[str]:
        missing: list[str] = []
        if not self.alan_mcp_url:
            missing.append("ALAN_MCP_URL")
        if not self.alan_mcp_token:
            missing.append("ALAN_MCP_TOKEN")
        if not self.alan_conversation_id:
            missing.append("ALAN_CONVERSATION_ID")
        if not self.alan_workflow_id:
            missing.append("ALAN_WORKFLOW_ID")
        return missing


def _build_settings() -> Settings:
    var_dir = Path(os.getenv("DOCUPILOT_VAR_DIR", str(PROJECT_ROOT / "var"))).resolve()
    cors = tuple(
        origin.strip()
        for origin in os.getenv(
            "DOCUPILOT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )
    return Settings(
        var_dir=var_dir,
        upload_dir=var_dir / "uploads",
        db_path=var_dir / "docupilot.sqlite3",
        max_upload_mb=_env_int("DOCUPILOT_MAX_UPLOAD_MB", 10),
        max_pdf_pages=_env_int("DOCUPILOT_MAX_PDF_PAGES", 5),
        max_image_pixels=_env_int("DOCUPILOT_MAX_IMAGE_PIXELS", 25_000_000),
        model_base_url=os.getenv(
            "ALAN_MODEL_BASE_URL", "https://api.tryalan.ai/public/harness/v1"
        ).rstrip("/"),
        model_api_key=os.getenv("ALAN_MODEL_API_KEY", "").strip(),
        model_name=os.getenv("ALAN_MODEL_NAME", "qwen/qwen3.8-27b").strip(),
        model_fallbacks=tuple(
            item.strip()
            for item in os.getenv(
                "ALAN_MODEL_FALLBACKS", "nvidia/nemotron-3-super-120b-a12b"
            ).split(",")
            if item.strip()
        ),
        model_timeout_seconds=_env_float("ALAN_MODEL_TIMEOUT_SECONDS", 90.0),
        model_max_tokens=_env_int("ALAN_MODEL_MAX_TOKENS", 2500),
        model_conversation_id=(
            os.getenv("ALAN_CONVERSATION_ID", "").strip()
            or os.getenv("ALAN_CODE_CONVERSATION_ID", "").strip()
        ),
        disable_model=_env_bool("DOCUPILOT_DISABLE_MODEL", False),
        alan_mcp_url=os.getenv("ALAN_MCP_URL", "https://api.tryalan.ai/mcp").strip(),
        alan_mcp_token=os.getenv("ALAN_MCP_TOKEN", "").strip(),
        alan_conversation_id=(
            os.getenv("ALAN_CONVERSATION_ID", "").strip()
            or os.getenv("ALAN_CODE_CONVERSATION_ID", "").strip()
        ),
        alan_workflow_id=os.getenv("ALAN_WORKFLOW_ID", "").strip(),
        alan_timeout_seconds=_env_int("ALAN_TIMEOUT_SECONDS", 300),
        alan_poll_seconds=_env_float("ALAN_POLL_SECONDS", 3.0),
        cors_origins=cors,
        auto_seed=_env_bool("DOCUPILOT_AUTO_SEED", True),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = _build_settings()
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


def reset_settings_cache() -> None:
    """Test helper: re-read the environment on the next get_settings() call."""
    get_settings.cache_clear()