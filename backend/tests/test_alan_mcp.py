from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.alan_mcp import (
    AlanNotConfigured,
    AlanWorkflowService,
    _dig,
    _execution_id,
    _status,
)


@pytest.fixture()
def alan_settings(settings):
    return replace(
        settings,
        alan_mcp_url="https://alan.example/mcp",
        alan_mcp_token="Bearer test-token",
        alan_conversation_id="conversation-test",
        alan_workflow_id="workflow-test",
    )


def test_alan_is_not_configured_without_all_four_values(settings, store):
    service = AlanWorkflowService(settings, store)
    assert service.enabled is False
    with pytest.raises(AlanNotConfigured) as excinfo:
        service.require()
    assert set(excinfo.value.missing) == {
        "ALAN_MCP_URL",
        "ALAN_MCP_TOKEN",
        "ALAN_CONVERSATION_ID",
        "ALAN_WORKFLOW_ID",
    }


def test_start_and_poll_use_real_execution_contract(alan_settings, store, make_demo_case):
    case = make_demo_case("northwind_inv_1042.pdf")
    service = AlanWorkflowService(alan_settings, store)

    class FakeMCP:
        def __init__(self):
            self.calls = []

        def tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "execute_workflow":
                return {"executionId": "exec-123", "status": "running"}
            return {
                "executionId": "exec-123",
                "status": "succeeded",
                "output": "FLAG-001 is the amount difference.",
                "url": "https://app.tryalan.ai/automations/run/exec-123",
            }

    fake = FakeMCP()
    service.client = fake  # type: ignore[assignment]

    # The service only needs compact_case_brief + flags_for from CaseService.
    class FakeCases:
        def compact_case_brief(self, detail):
            return '{"case_id":"demo"}'

        def flags_for(self, detail):
            return detail.match.flags if detail.match else []

    investigation = service.start(case, "Why the difference?", FakeCases())  # type: ignore[arg-type]
    assert investigation.execution_id == "exec-123"
    assert investigation.case_id == case.id
    assert investigation.status == "running"
    assert fake.calls[0][0] == "execute_workflow"
    assert fake.calls[0][1]["workflowId"] == "workflow-test"
    assert "case_brief" in fake.calls[0][1]["triggerPayload"]

    polled = service.poll("exec-123")
    assert polled.status == "succeeded"
    assert "FLAG-001" in (polled.output or "")
    assert polled.polls == 1
    assert fake.calls[1] == (
        "workflow_execution",
        {"op": "get", "executionId": "exec-123"},
    )

    # Terminal runs are not polled again.
    again = service.poll("exec-123")
    assert again.status == "succeeded"
    assert len(fake.calls) == 2


def test_alan_payload_parsing():
    nested = {
        "result": {
            "execution": {
                "executionId": "exec-9",
                "status": "succeeded",
                "output": "done",
                "url": "https://example/run",
            }
        }
    }
    assert _execution_id(nested) == "exec-9"
    assert _status(nested) == "succeeded"
    assert _dig(nested, "output") == "done"
