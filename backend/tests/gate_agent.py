"""Agent-loop integration gate: the REAL AirlockAgent path, LLM mocked at HTTP only.

The model transport returns a scripted conversation (plan → run_python → final answer),
while everything else — tool dispatch, sandbox execution, receipts, artifacts — is the
production code path. When the real API key arrives, only the HTTP boundary changes.

Run: .venv/bin/python tests/gate_agent.py
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("VULTR_INFERENCE_API_KEY", "test-key-for-mocks")
os.environ["AIRLOCK_MODEL_CHAIN"] = "mock-model"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.agent import AirlockAgent  # noqa: E402
from app.receipts import verify_receipt  # noqa: E402
from app.vultr_client import VultrClient  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name} {detail}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")


def completion(model, content=None, tool_calls=None, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
            for c in tool_calls
        ]
    return {"model": model, "usage": {},
            "choices": [{"message": msg, "finish_reason": finish}]}


def main() -> None:
    script = [
        # turn 1: model asks to inspect the file
        completion("mock-model", tool_calls=[
            {"id": "c1", "name": "run_python",
             "args": {"code": "import pandas as pd\n"
                              "df = pd.read_csv('/work/input/data.csv')\n"
                              "print(df.groupby('region')['revenue'].sum().to_string())\n"}},
        ], finish="tool_calls"),
        # turn 2: model charts
        completion("mock-model", tool_calls=[
            {"id": "c2", "name": "run_python",
             "args": {"code": "import pandas as pd, matplotlib\n"
                              "matplotlib.use('Agg')\n"
                              "import matplotlib.pyplot as plt\n"
                              "df = pd.read_csv('/work/input/data.csv')\n"
                              "df.groupby('region')['revenue'].sum().plot.bar()\n"
                              "plt.tight_layout(); plt.savefig('/work/output/revenue.png')\n"
                              "print('chart written')\n"}},
        ], finish="tool_calls"),
        # turn 3: unknown tool (must be handled gracefully) then final answer
        completion("mock-model", tool_calls=[
            {"id": "c3", "name": "delete_everything", "args": {}},
        ], finish="tool_calls"),
        completion("mock-model", content="East has the highest revenue (5900). Chart: revenue.png",
                   finish="stop"),
        # turn 5: vision QA call (image content) answered by the omni model
        completion("mock-model", content="PASS: legible bar chart of revenue by region"),
    ]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        r = script[calls["n"]]
        calls["n"] += 1
        return httpx.Response(200, json=r)

    csv = (b"region,units,revenue\nnorth,120,4800\nsouth,80,3100\n"
           b"east,150,5900\nwest,95,3700\n")
    agent = AirlockAgent(VultrClient(transport=httpx.MockTransport(handler)))
    outcome = agent.run_task("Which region has the highest revenue? Chart it.",
                             csv=("data.csv", csv), task_id="agentgate001")

    check("agent completed", outcome.status == "completed", outcome.error)
    check("answer from final turn", "East has the highest revenue" in outcome.answer)
    check("model recorded", outcome.model_used == "mock-model")
    check("four LLM turns + one vision QA call", calls["n"] == 5, f"n={calls['n']}")

    check("chart artifact collected",
          any(a["name"] == "revenue.png" for a in outcome.artifacts),
          str([a["name"] for a in outcome.artifacts]))

    receipt = json.loads(Path(outcome.receipt_path).read_text())
    types = [e["type"] for e in receipt["events"]]
    check("receipt has full lifecycle",
          all(t in types for t in ("TASK_CREATED", "DATA_SEALED", "SANDBOX_CREATED",
                                   "TOOL_CALL", "SANDBOX_DESTROYED", "TASK_COMPLETED",
                                   "RECEIPT_SEALED")),
          str(types))
    check("unknown tool handled gracefully",
          any(e["detail"].get("tool") == "delete_everything" for e in receipt["events"]
              if e["type"] == "TOOL_CALL"),
          "flow continued to a final answer after the unknown tool")
    v = verify_receipt(Path(outcome.receipt_path))
    check("receipt chain verifies", v["valid"], str(v))

    check("vision QA ran on the chart",
          any(e["type"] == "VISION_QA" and "PASS" in str(e["detail"].get("verdict", ""))
              for e in receipt["events"]))
    check("vision verdict attached to artifact",
          "vision_qa" in outcome.artifacts[0])

    # artifact served bytes are a real PNG
    png = Path(outcome.artifacts[0]["path"]).read_bytes()
    check("artifact is a real PNG", png[:8] == b"\x89PNG\r\n\x1a\n", f"{len(png)} bytes")

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
