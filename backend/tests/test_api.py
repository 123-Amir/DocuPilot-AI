from __future__ import annotations

from pathlib import Path

import pymupdf

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def _upload(client, filename: str, content_type: str | None = None):
    data = (SAMPLES / filename).read_bytes()
    if content_type is None:
        content_type = "application/pdf" if filename.endswith(".pdf") else "image/png"
    return client.post(
        "/api/documents",
        files={"file": (filename, data, content_type)},
    )


def test_health_reports_real_capability_state(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True
    assert body["model_configured"] is False
    assert body["alan_workflow_configured"] is False
    assert "ALAN_MCP_URL" in body["alan_missing"]
    assert "never" in body["warning"].lower() or "does not" in body["warning"].lower()


def test_upload_extract_match_and_preview(client):
    response = _upload(client, "northwind_inv_1042.pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "no_mismatch"
    assert body["invoice"]["vendor_name"] == "Northwind Office Supply"
    assert body["invoice"]["invoice_number"] == "NW-INV-1042"
    assert body["match"]["flags"] == []
    assert body["document_url"] == f"/api/cases/{body['id']}/document"

    detail = client.get(f"/api/cases/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["model"]["mode"] == "fixture"

    preview = client.get(f"/api/cases/{body['id']}/document")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("application/pdf")
    assert preview.headers["x-content-type-options"] == "nosniff"


def test_review_is_human_only_and_persists(client):
    case = _upload(client, "meridian_inv_88213.pdf").json()
    response = client.post(
        f"/api/cases/{case['id']}/review",
        json={
            "status": "needs_vendor_contact",
            "note": "Seller billed 0.25 above the agreed unit price.",
            "reviewer": "Demo Reviewer",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review"]["status"] == "needs_vendor_contact"
    assert body["review"]["reviewer"] == "Demo Reviewer"
    assert body["review"]["updated_at"]

    again = client.get(f"/api/cases/{case['id']}").json()
    assert again["review"]["status"] == "needs_vendor_contact"


def test_chat_uses_deterministic_fallback_and_cites_flags(client):
    case = _upload(client, "meridian_inv_88213.pdf").json()
    response = client.post(
        f"/api/cases/{case['id']}/chat",
        json={"message": "Why is the total different?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "deterministic fallback" in body["source"]
    assert "1,265.00" in body["message"]["content"]
    assert body["citations"]
    assert all(item.startswith("FLAG-") for item in body["citations"])

    refusal = client.post(
        f"/api/cases/{case['id']}/chat",
        json={"message": "Can you approve this invoice and pay it?"},
    ).json()
    assert "cannot approve" in refusal["message"]["content"].lower()

    messages = client.get(f"/api/cases/{case['id']}/messages").json()
    assert len(messages) == 4
    assert [item["role"] for item in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_dashboard_counts_flags_and_statuses(client):
    _upload(client, "northwind_inv_1042.pdf")
    _upload(client, "meridian_inv_88213.pdf")
    _upload(client, "aster_inv_5591.png")

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["stats"]["total_documents"] == 3
    assert dashboard["stats"]["needs_review"] == 2
    assert dashboard["stats"]["no_mismatch"] == 1
    assert dashboard["stats"]["high_flags"] >= 3
    codes = {item["code"] for item in dashboard["flag_counts"]}
    assert {"total_mismatch", "vendor_mismatch", "missing_field"} <= codes
    assert len(dashboard["recent"]) == 3


def test_invalid_upload_returns_clear_error(client):
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"just some notes", "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "unsupported_extension"
    assert "PDF" in body["error"]["message"]


def test_arbitrary_pdf_without_model_is_not_faked(client):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "INVOICE\nVendor: Unknown Co\nTotal: 100.00")
    data = document.tobytes()
    document.close()

    response = client.post(
        "/api/documents",
        files={"file": ("unknown.pdf", data, "application/pdf")},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_not_configured"

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["stats"]["failed"] == 1


def test_alan_escalation_is_gated_not_faked(client):
    case = _upload(client, "northwind_inv_1042.pdf").json()
    response = client.post(
        f"/api/cases/{case['id']}/alan/investigations",
        json={"question": "What should we check?"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "alan_not_configured"
    assert "ALAN_WORKFLOW_ID" in body["error"]["missing"]
    assert client.get(f"/api/cases/{case['id']}/alan/investigations").json() == []


def test_missing_case_returns_404(client):
    response = client.get("/api/cases/CASE-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"


def test_empty_chat_message_is_rejected(client):
    case = _upload(client, "northwind_inv_1042.pdf").json()
    response = client.post(f"/api/cases/{case['id']}/chat", json={"message": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"