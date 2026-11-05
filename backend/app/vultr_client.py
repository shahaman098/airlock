"""Vultr Serverless Inference client.

All LLM traffic goes to https://api.vultrinference.com/v1 (OpenAI-compatible).
Verified behaviours this client relies on:
  * POST /chat/completions with OpenAI `tools[]` and `tool_choice`
  * `finish_reason: "tool_calls"` + follow-up `role:"tool"` message (tools[] re-sent)
  * rate limits 120 RPM / 16 concurrent per model -> exponential backoff on 429/504
  * model IDs churn upstream -> chain falls forward if a model 404s or rejects tools
"""
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class VultrInferenceError(RuntimeError):
    pass


class VultrClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.vultr_api_key:
            raise VultrInferenceError(
                "VULTR_INFERENCE_API_KEY is not set. Create one at console.vultr.com/inference."
            )
        self._http = httpx.Client(
            base_url=settings.inference_base_url,
            headers={"Authorization": f"Bearer {settings.vultr_api_key}"},
            timeout=settings.request_timeout_s,
            transport=transport,
        )
        self._tools_ok: dict[str, bool] = {}  # model -> supports tool calling (observed)

    # -- models ------------------------------------------------------------
    def list_models(self) -> list[str]:
        r = self._http.get("/models")
        r.raise_for_status()
        data = r.json().get("data", [])
        return sorted(m.get("id", "") for m in data)

    # -- chat --------------------------------------------------------------
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> ChatResult:
        """Try the model chain in order; fall forward on missing model / tool rejection."""
        errors: list[str] = []
        for model in settings.model_chain:
            if tools and self._tools_ok.get(model) is False:
                continue
            try:
                return self._chat_one(messages, tools, model)
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                errors.append(f"{model}: HTTP {code}")
                if code in (429, 502, 503, 504):
                    continue  # also try next model; backoff handled inside _chat_one first
                if code == 400 and tools:
                    self._tools_ok[model] = False
                    continue
                if code == 404:
                    continue
                raise VultrInferenceError(f"{model}: HTTP {code}: {exc.response.text[:300]}") from exc
            except httpx.HTTPError as exc:
                errors.append(f"{model}: {type(exc).__name__}")
                continue
        raise VultrInferenceError("all models in chain failed: " + "; ".join(errors))

    def _chat_one(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, model: str) -> ChatResult:
        body: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        delay = 1.0
        for attempt in range(settings.max_retries):
            r = self._http.post("/chat/completions", json=body)
            if r.status_code == 429 or r.status_code in (502, 503, 504):
                if attempt == settings.max_retries - 1:
                    r.raise_for_status()
                retry_after = r.headers.get("retry-after")
                time.sleep(float(retry_after) if retry_after else delay)
                delay *= 2
                continue
            r.raise_for_status()
            self._tools_ok.setdefault(model, True)
            return self._parse(r.json(), model)

        raise VultrInferenceError(f"{model}: retries exhausted")

    @staticmethod
    def _parse(payload: dict[str, Any], model: str) -> ChatResult:
        choices = payload.get("choices") or []
        if not choices:
            raise VultrInferenceError(f"{model}: empty choices in response")
        choice = choices[0]
        msg = choice.get("message", {})
        calls = [
            ToolCall(id=c.get("id", ""), name=c.get("function", {}).get("name", ""),
                     arguments=c.get("function", {}).get("arguments", "{}"))
            for c in msg.get("tool_calls", []) or []
        ]
        return ChatResult(
            content=msg.get("content"),
            tool_calls=calls,
            model=payload.get("model", model),
            finish_reason=choice.get("finish_reason", ""),
            usage=payload.get("usage", {}),
        )

    # -- vision ------------------------------------------------------------
    def vision_check(self, png_bytes: bytes, question: str | None = None) -> str:
        """Ask the vision-capable omni model whether a chart rendered correctly.

        Best-effort by design: callers treat any failure as 'unverified', never fatal.
        """
        import base64

        prompt = question or (
            "This image was produced by matplotlib inside a sandbox. Answer in one short "
            "sentence: does it show a legible, non-empty chart (title/axes/bars visible)? "
            "Reply 'PASS: <what it shows>' or 'FAIL: <why>'."
        )
        body = {
            "model": settings.vision_model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(png_bytes).decode()
                    }},
                ],
            }],
        }
        r = self._http.post("/chat/completions", json=body)
        r.raise_for_status()
        choices = r.json().get("choices") or []
        if not choices:
            raise VultrInferenceError("empty vision response")
        return (choices[0].get("message", {}).get("content") or "").strip()

    def close(self) -> None:
        self._http.close()
