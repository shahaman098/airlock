"""Inference-client gate: prove the Vultr client's logic without a live key.

Mocked at the HTTP boundary (httpx.MockTransport) so the tool-call contract,
model fallback chain and backoff behaviour are verified now — when the real key
arrives, only live behaviour (model IDs, per-model tool support) remains to check.

Run: .venv/bin/python tests/gate_inference.py
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("VULTR_INFERENCE_API_KEY", "test-key-for-mocks")
os.environ["AIRLOCK_MODEL_CHAIN"] = "model-a,model-b,model-c"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app import config  # noqa: E402
config.settings.max_retries = 3
config.settings.model_chain = ["model-a", "model-b", "model-c"]

from app.vultr_client import ToolCall, VultrClient, VultrInferenceError  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name} {detail}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")


def completion(model: str, content=None, tool_calls=None, finish="stop") -> dict:
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
            for c in tool_calls
        ]
    return {"model": model, "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"message": msg, "finish_reason": finish}]}


def make_client(handler) -> VultrClient:
    return VultrClient(transport=httpx.MockTransport(handler))


def main() -> None:
    tools = [{"type": "function", "function": {"name": "run_python", "parameters": {}}}]

    # 1. tool-call round trip parses correctly
    def h1(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["tools"][0]["function"]["name"] == "run_python"
        if len(body["messages"]) == 1:
            return httpx.Response(200, json=completion(
                "model-a", tool_calls=[{"id": "t1", "name": "run_python", "args": {"code": "print(1)"}}],
                finish="tool_calls"))
        # follow-up must include the tool message and RE-SEND tools[]
        assert body["messages"][-1]["role"] == "tool" and body["messages"][-1]["tool_call_id"] == "t1"
        assert "tools" in body, "tools[] must be re-sent on follow-up"
        return httpx.Response(200, json=completion("model-a", content="done"))

    c = make_client(h1)
    r1 = c.chat([{"role": "user", "content": "x"}], tools=tools)
    check("tool_calls parsed", r1.finish_reason == "tool_calls"
          and r1.tool_calls[0].name == "run_python"
          and json.loads(r1.tool_calls[0].arguments)["code"] == "print(1)")
    follow_up = [{"role": "user", "content": "x"},
                 {"role": "assistant", "content": None, "tool_calls": [
                     {"id": "t1", "type": "function",
                      "function": {"name": "run_python", "arguments": "{}"}}]},
                 {"role": "tool", "tool_call_id": "t1", "content": "out"}]
    r2 = c.chat(follow_up, tools=tools)
    check("final answer after tool result", r2.content == "done" and r2.model == "model-a")

    # 2. 404 on first model -> falls forward in the chain
    def h2(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "model-a":
            return httpx.Response(404, json={"error": "no such model"})
        return httpx.Response(200, json=completion("model-b", content="from b"))

    r = make_client(h2).chat([{"role": "user", "content": "x"}])
    check("404 falls to next model", r.model == "model-b" and r.content == "from b")

    # 3. 400 with tools -> model marked tool-incapable, skipped afterwards
    calls = {"a": 0}

    def h3(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "model-a":
            calls["a"] += 1
            return httpx.Response(400, json={"error": "tools not supported"})
        return httpx.Response(200, json=completion("model-b", content="ok"))

    c3 = make_client(h3)
    r = c3.chat([{"role": "user", "content": "x"}], tools=tools)
    check("400 w/ tools falls forward", r.model == "model-b")
    c3.chat([{"role": "user", "content": "x"}], tools=tools)
    check("tool-incapable model skipped on next call", calls["a"] == 1, f"model-a hits={calls['a']}")

    # 4. 429 with Retry-After -> retries, then succeeds
    attempts = {"n": 0}

    def h4(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(429, headers={"retry-after": "0.05"}, json={})
        return httpx.Response(200, json=completion("model-a", content="recovered"))

    t0 = time.monotonic()
    r = make_client(h4).chat([{"role": "user", "content": "x"}])
    took = time.monotonic() - t0
    check("429 backoff then success", r.content == "recovered" and attempts["n"] == 3
          and took >= 0.06, f"attempts={attempts['n']} took={took:.2f}s")

    # 5. everything fails -> explicit error, not a crash
    def h5(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    try:
        make_client(h5).chat([{"role": "user", "content": "x"}])
        check("all-models-fail raises", False)
    except VultrInferenceError as exc:
        check("all-models-fail raises", "all models in chain failed" in str(exc))

    # 6. missing key is a clear error
    os.environ["VULTR_INFERENCE_API_KEY"] = ""
    from app import config as cfg2
    cfg2.settings.vultr_api_key = ""
    try:
        VultrClient()
        check("missing key raises clear error", False)
    except VultrInferenceError as exc:
        check("missing key raises clear error", "console.vultr.com/inference" in str(exc))

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
