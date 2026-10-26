"""Alan product integration over the documented MCP endpoint.

DocuPilot does not invent an SDK. It speaks JSON-RPC to the Alan MCP server
(``ALAN_MCP_URL``) with the hackathon account token, executes a pre-created Alan
workflow, and polls the real execution record.

The chat itself uses Alan's OpenAI-compatible model gateway. Workflow escalation
is optional and explicitly gated: if the workflow ID is absent, the UI shows the
missing configuration instead of a dead button.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.db import Store, utcnow
from app.schemas import AlanInvestigation, CaseDetail
from app.services.cases import CaseService

TERMINAL_STATUSES = {
    "succeeded",
    "completed",
    "failed",
    "interrupted",
    "cancelled",
    "timed_out",
    "skipped",
}


class AlanIntegrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AlanNotConfigured(AlanIntegrationError):
    def __init__(self, missing: list[str]):
        super().__init__(
            "alan_not_configured",
            "Alan workflow escalation is not configured. Missing server-side "
            f"variables: {', '.join(missing)}. The chat still works through the Alan "
            "model gateway; no workflow run is claimed.",
            503,
        )
        self.missing = missing


class AlanMCPClient:
    def __init__(self, url: str, token: str, conversation_id: str, timeout: float = 60.0):
        self.url = url
        self.token = token
        self.conversation_id = conversation_id
        self.timeout = timeout
        self._counter = 0

    def _headers(self) -> dict[str, str]:
        token = self.token if self.token.lower().startswith("bearer ") else f"Bearer {self.token}"
        return {
            "Authorization": token,
            "x-alan-conversation-id": self.conversation_id,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _parse_payload(self, text: str, content_type: str) -> dict[str, Any]:
        stripped = text.strip()
        if not stripped:
            raise AlanIntegrationError("empty_response", "Alan MCP returned an empty response.")
        if "event:" in stripped or stripped.startswith("data:"):
            candidates: list[str] = []
            for block in stripped.split("\n\n"):
                data_lines = [
                    line[5:].strip()
                    for line in block.splitlines()
                    if line.startswith("data:")
                ]
                if data_lines:
                    candidates.append("".join(data_lines))
            for candidate in reversed(candidates):
                try:
                    value = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    return value
            raise AlanIntegrationError(
                "invalid_response", "Alan MCP returned an unreadable event stream."
            )
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AlanIntegrationError(
                "invalid_response", "Alan MCP returned a non-JSON response."
            ) from exc
        if not isinstance(value, dict):
            raise AlanIntegrationError("invalid_response", "Alan MCP returned an unexpected payload.")
        return value

    def rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._counter += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._counter,
            "method": method,
            "params": params,
        }
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.post(self.url, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise AlanIntegrationError(
                "alan_unreachable",
                "Could not reach the Alan MCP endpoint. Check ALAN_MCP_URL and network access.",
            ) from exc

        if response.status_code in {401, 403}:
            raise AlanIntegrationError(
                "alan_unauthorized",
                "Alan rejected the MCP credential. The token must be a current "
                "server-side Alan MCP token; never put it in the frontend.",
                502,
            )
        if response.status_code == 404:
            raise AlanIntegrationError(
                "alan_not_found", "The Alan MCP endpoint returned 404. Check ALAN_MCP_URL."
            )
        if response.status_code >= 400:
            raise AlanIntegrationError(
                "alan_http_error",
                f"Alan MCP returned HTTP {response.status_code}.",
            )

        data = self._parse_payload(response.text, response.headers.get("content-type", ""))
        if data.get("error"):
            error = data["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise AlanIntegrationError(
                "alan_tool_error", f"Alan MCP rejected the call: {message}"
            )
        if "result" not in data:
            raise AlanIntegrationError("invalid_response", "Alan MCP response has no result.")
        return data["result"]

    def tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if not isinstance(result, dict):
            raise AlanIntegrationError("invalid_response", "Alan tool result is not an object.")
        if result.get("isError"):
            text = _content_text(result) or "Alan tool reported an error."
            raise AlanIntegrationError("alan_tool_error", text)
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        text = _content_text(result)
        if not text:
            return result
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"text": text}
        except json.JSONDecodeError:
            return {"text": text}


def _content_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def _dig(source: Any, *keys: str, depth: int = 0) -> Any:
    """Find the first matching key in a nested MCP payload."""
    if depth > 4 or not isinstance(source, dict):
        return None
    for key in keys:
        if key in source and source[key] not in (None, ""):
            return source[key]
    for value in source.values():
        found = _dig(value, *keys, depth=depth + 1)
        if found not in (None, ""):
            return found
    return None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:12000]
    try:
        return json.dumps(value, ensure_ascii=False)[:12000]
    except (TypeError, ValueError):
        return str(value)[:12000]


def _execution_id(result: dict[str, Any]) -> str | None:
    value = _dig(result, "executionId", "execution_id", "runId", "run_id", "id")
    return str(value) if value else None


def _status(result: dict[str, Any], default: str = "pending") -> str:
    value = _dig(result, "status", "state")
    return str(value).lower() if value else default


class AlanWorkflowService:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store
        self.client = AlanMCPClient(
            settings.alan_mcp_url,
            settings.alan_mcp_token,
            settings.alan_conversation_id,
        )

    @property
    def enabled(self) -> bool:
        return self.settings.alan_workflow_enabled

    def require(self) -> None:
        if not self.enabled:
            raise AlanNotConfigured(self.settings.alan_missing)

    def start(
        self, detail: CaseDetail, question: str, cases: CaseService
    ) -> AlanInvestigation:
        self.require()
        brief = cases.compact_case_brief(detail)
        payload = {
            "case_id": detail.id,
            "case_brief": brief,
            "question": question,
            "flag_ids": [flag.id for flag in cases.flags_for(detail)],
        }
        result = self.client.tool(
            "execute_workflow",
            {
                "workflowId": self.settings.alan_workflow_id,
                "triggerPayload": payload,
            },
        )
        execution_id = _execution_id(result)
        if not execution_id:
            raise AlanIntegrationError(
                "missing_execution_id",
                "Alan accepted the tool call but returned no workflow execution ID. "
                "No investigation was started.",
            )
        now = utcnow()
        investigation = AlanInvestigation(
            execution_id=execution_id,
            case_id=detail.id,
            workflow_id=self.settings.alan_workflow_id,
            status=_status(result),
            question=question,
            output=_as_text(_dig(result, "output", "result", "summary")),
            error=_as_text(_dig(result, "error")),
            started_at=now,
            updated_at=now,
            url=_dig(result, "url", "link"),
            polls=0,
        )
        self.store.save_alan_run(detail.id, investigation.model_dump(mode="json"))
        return investigation

    def poll(self, execution_id: str) -> AlanInvestigation:
        self.require()
        current = self.store.get_alan_run(execution_id)
        if current is None:
            raise AlanIntegrationError(
                "alan_run_not_found", "No stored Alan investigation has that execution ID.", 404
            )
        investigation = AlanInvestigation.model_validate(current)
        if investigation.status in TERMINAL_STATUSES:
            return investigation

        result = self.client.tool(
            "workflow_execution",
            {"op": "get", "executionId": execution_id},
        )
        investigation.status = _status(result, default=investigation.status)
        investigation.output = (
            _as_text(_dig(result, "output", "result", "summary")) or investigation.output
        )
        investigation.error = _as_text(_dig(result, "error")) or investigation.error
        investigation.url = _dig(result, "url", "link") or investigation.url
        investigation.polls += 1
        investigation.updated_at = utcnow()
        case_id = investigation.case_id
        if not case_id:
            raise AlanIntegrationError(
                "alan_run_not_found",
                "The stored Alan investigation has no owning case.",
                404,
            )
        self.store.save_alan_run(case_id, investigation.model_dump(mode="json"))
        return investigation

    def list_for_case(self, case_id: str) -> list[AlanInvestigation]:
        return [
            AlanInvestigation.model_validate(item)
            for item in self.store.list_alan_runs(case_id)
        ]