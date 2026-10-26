from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings, get_settings  # noqa: E402
from app.db import Store  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.cases import CaseService  # noqa: E402

SAMPLES = BACKEND_ROOT / "samples"


@pytest.fixture(scope="session", autouse=True)
def ensure_samples() -> None:
    if not (SAMPLES / "manifest.json").exists():
        subprocess.run(
            [sys.executable, str(BACKEND_ROOT / "scripts" / "generate_samples.py")],
            check=True,
        )


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    base = get_settings()
    return replace(
        base,
        var_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        db_path=tmp_path / "docupilot-test.sqlite3",
        samples_dir=SAMPLES,
        po_file=BACKEND_ROOT / "app" / "data" / "purchase_orders.json",
        disable_model=True,
        auto_seed=False,
        alan_mcp_url="",
        alan_mcp_token="",
        alan_conversation_id="",
        alan_workflow_id="",
    )


@pytest.fixture()
def store(settings: Settings):
    instance = Store(settings.db_path)
    yield instance
    instance.close()


@pytest.fixture()
def service(settings: Settings, store: Store) -> CaseService:
    return CaseService(settings, store)


@pytest.fixture()
def client(settings: Settings, store: Store):
    app = create_app(settings, store)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def make_demo_case(service: CaseService):
    def _make(filename: str):
        path = SAMPLES / filename
        content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "image/png"
        return service.create_document(
            path.read_bytes(),
            path.name,
            content_type,
            source="demo",
            force_fixture=True,
        )

    return _make