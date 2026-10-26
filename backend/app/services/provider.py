"""Open-model client for the hackathon Alan model gateway.

The gateway is OpenAI-compatible and was verified against this account at
``POST {ALAN_MODEL_BASE_URL}/chat/completions``. Credentials stay on the server;
the browser never receives the API key.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class ModelUnavailable(RuntimeError):
    """Raised when no model credential is configured."""


class ModelCallError(RuntimeError):
    """Raised for transport, auth, or response-shape failures."""


def _retry_after_seconds(response: httpx.Response) -> float:
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        body = response.json()
        value = body.get("retryAfterSeconds")
        if isinstance(value, (int, float)):
            return float(value)
    except (ValueError, AttributeError):
        pass
    return 2.0


@dataclass
class ModelReply:
    content: str
    model: str
    elapsed_ms: int
    usage: dict[str, Any]

    @property
    def display_source(self) -> str:
        return f"{self.model} via Alan model gateway"


class AlanModelClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.model_enabled

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.model_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.model_conversation_id:
            headers["x-alan-conversation-id"] = self.settings.model_conversation_id
        return headers

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        fallback_models: list[str] | None = None,
    ) -> ModelReply:
        if not self.enabled:
            raise ModelUnavailable(
                "No Alan model credential is configured. Set ALAN_MODEL_API_KEY "
                "in the server environment."
            )

        models = [self.settings.model_name]
        models.extend(
            self.settings.model_fallbacks
            if fallback_models is None
            else fallback_models
        )
        models = list(dict.fromkeys(model for model in models if model))

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.settings.model_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.settings.model_base_url}/chat/completions"
        started = time.perf_counter()
        last_error = ModelCallError("No model was attempted.")

        for index, model in enumerate(models):
            payload["model"] = model
            is_last = index == len(models) - 1

            for attempt in range(2):
                try:
                    with httpx.Client(
                        timeout=self.settings.model_timeout_seconds,
                        follow_redirects=False,
                    ) as client:
                        response = client.post(
                            url, headers=self._headers(), json=payload
                        )
                except httpx.HTTPError as exc:
                    last_error = ModelCallError(
                        "The Alan model gateway could not be reached. Check your "
                        "network and ALAN_MODEL_BASE_URL."
                    )
                    logger.warning(
                        "model transport error model=%s attempt=%s: %s",
                        model,
                        attempt + 1,
                        exc,
                    )
                    break

                if response.status_code == 400 and "response_format" in payload:
                    # Some OpenAI-compatible routes reject response_format. Retry
                    # the same model without it and rely on the JSON parser.
                    payload.pop("response_format", None)
                    continue

                if response.status_code in {401, 403}:
                    raise ModelCallError(
                        "The Alan model gateway rejected the credential. Regenerate "
                        "ALAN_MODEL_API_KEY and keep it server-side."
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    snippet = response.text[:200].replace("\n", " ")
                    last_error = ModelCallError(
                        f"The Alan model gateway returned {response.status_code}: {snippet}"
                    )
                    logger.warning(
                        "model upstream error model=%s status=%s attempt=%s: %s",
                        model,
                        response.status_code,
                        attempt + 1,
                        snippet,
                    )
                    if not is_last:
                        break
                    if attempt == 0:
                        time.sleep(min(max(_retry_after_seconds(response), 1.0), 8.0))
                        continue
                    raise last_error

                if response.status_code >= 400:
                    detail = response.text[:300]
                    raise ModelCallError(
                        f"The Alan model gateway returned {response.status_code}: {detail}"
                    )

                try:
                    data = response.json()
                except ValueError as exc:
                    raise ModelCallError(
                        "The Alan model gateway returned a non-JSON response."
                    ) from exc

                try:
                    choice = data["choices"][0]["message"]
                    content = choice.get("content") or ""
                    if not isinstance(content, str):
                        content = str(content)
                    if not content.strip():
                        content = choice.get("reasoning") or ""
                except (KeyError, IndexError, TypeError) as exc:
                    raise ModelCallError(
                        "The Alan model gateway response did not include a message."
                    ) from exc

                if not content.strip():
                    last_error = ModelCallError(
                        f"The model {model} returned an empty message."
                    )
                    if not is_last:
                        break
                    raise last_error

                elapsed_ms = int((time.perf_counter() - started) * 1000)
                used_model = str(data.get("model") or model)
                logger.info(
                    "model call ok requested=%s used=%s elapsed_ms=%s usage=%s",
                    model,
                    used_model,
                    elapsed_ms,
                    data.get("usage"),
                )
                return ModelReply(
                    content=content.strip(),
                    model=used_model,
                    elapsed_ms=elapsed_ms,
                    usage=data.get("usage") or {},
                )

        raise last_error