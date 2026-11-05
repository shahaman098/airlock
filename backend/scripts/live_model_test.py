"""Zero-thought key onboarding: paste the key, run this, get a verdict.

Tests every model in the chain against the LIVE Vultr Serverless Inference:
  1. basic completion          2. tool-calling round-trip
  3. vision check (omni model) with a real generated chart
Prints the verified chain to put in .env, so deployment uses only proven models.

Run:  .venv/bin/python scripts/live_model_test.py
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.vultr_client import VultrClient, VultrInferenceError  # noqa: E402

TOOLS = [{"type": "function", "function": {
    "name": "echo_test",
    "description": "Echo a test string.",
    "parameters": {"type": "object", "properties": {"s": {"type": "string"}}, "required": ["s"]},
}}]


def make_chart_png() -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3, 2))
    ax.bar(["a", "b", "c"], [3, 1, 2])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


def main() -> int:
    if not settings.vultr_api_key:
        print("No API key found. Put VULTR_INFERENCE_API_KEY=... in backend/.env and rerun.")
        return 2

    client = VultrClient()
    t0 = time.time()
    try:
        models = client.list_models()
        print(f"reachable · {len(models)} models listed ({time.time()-t0:.1f}s)")
    except Exception as exc:  # noqa: BLE001
        print(f"UNREACHABLE: {exc}")
        return 2

    print(f"\n{'model':44s} {'chat':6s} {'tools':6s} latency")
    proven: list[str] = []
    for model in settings.model_chain:
        chat_ok = tools_ok = False
        lat = "—"
        try:
            t = time.time()
            r = client._chat_one([{"role": "user", "content": "Say OK."}], None, model)
            chat_ok = bool(r.content)
            lat = f"{time.time()-t:.1f}s"
        except Exception as exc:  # noqa: BLE001
            lat = f"err: {str(exc)[:60]}"
        if chat_ok:
            try:
                r = client.chat([{"role": "user", "content": "Call echo_test with s='ping'."}],
                                tools=TOOLS)
                tools_ok = r.finish_reason == "tool_calls" and r.tool_calls[0].name == "echo_test"
            except Exception:  # noqa: BLE001
                tools_ok = False
        mark = lambda ok: "OK" if ok else "—"  # noqa: E731
        print(f"{model:44s} {mark(chat_ok):6s} {mark(tools_ok):6s} {lat}")
        if chat_ok:
            proven.append(model)

    vision_ok = "—"
    try:
        verdict = client.vision_check(make_chart_png())
        vision_ok = "OK" if verdict.upper().startswith("PASS") else f"verdict: {verdict[:60]}"
    except Exception as exc:  # noqa: BLE001
        vision_ok = f"err: {str(exc)[:60]}"
    print(f"\nvision model ({settings.vision_model}): {vision_ok}")

    print("\n==> verified chain for backend/.env:")
    print("AIRLOCK_MODEL_CHAIN=" + ",".join(proven or settings.model_chain))
    print("\n==> next: ./deploy/deploy.sh root@VM_IP")
    return 0 if proven else 1


if __name__ == "__main__":
    sys.exit(main())
