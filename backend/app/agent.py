"""Airlock agent: an LLM data analyst whose only hands are jailed tools.

The model never runs anywhere but Vultr Serverless Inference; the only way it can
touch the user's data is by writing Python that executes inside the sandbox.
Every step lands in the containment receipt.
"""
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import WORKSPACES_DIR, settings
from .receipts import Receipt
from .sandbox import Sandbox
from .vultr_client import ToolCall, VultrClient

Event = Callable[[str, dict[str, Any]], None]

SYSTEM_PROMPT = """You are Airlock's data analyst. You answer questions about files in /work/input
by writing Python 3 that runs inside a sealed, network-isolated sandbox (pandas, numpy and
matplotlib are available). Rules:
- ALWAYS use the run_python tool to inspect or transform data; never guess about the data.
- Write charts to /work/output/ as PNG files (matplotlib, Agg backend is set).
- Print concise, readable results to stdout — they are shown to the user.
- If a run fails, read the error and fix your code. Up to a few attempts.
- When you have enough evidence, reply with a short, direct answer that cites the numbers
  you found, and name any chart files you produced.
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Run Python 3 code inside the sealed sandbox. pandas/numpy/matplotlib available. Files are at /work/input; write artifacts to /work/output. Returns stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python source to execute."}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the files available in /work/input and /work/output.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class TaskOutcome:
    task_id: str
    question: str
    answer: str = ""
    model_used: str = ""
    iterations: int = 0
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    receipt_path: str = ""
    status: str = "completed"  # completed | failed
    error: str = ""


class AirlockAgent:
    def __init__(self, client: VultrClient, on_event: Event | None = None):
        self.client = client
        self.on_event = on_event or (lambda t, d: None)

    def _emit(self, event_type: str, **detail: Any) -> None:
        self.on_event(event_type, detail)

    # -- tools -------------------------------------------------------------
    def _tool_list_files(self, ws: Path) -> str:
        def listing(sub: str) -> str:
            d = ws / sub
            if not d.exists():
                return f"{sub}: (missing)"
            files = sorted(p.name for p in d.iterdir() if p.is_file())
            return f"{sub}: {', '.join(files) if files else '(empty)'}"

        return "\n".join([listing("input"), listing("output")])

    def _tool_run_python(self, code: str, ws: Path, receipt: Receipt) -> str:
        sb = Sandbox(on_event=lambda t, d: receipt.add(t, **d))
        result = sb.run(code, workspace=ws)
        if result.termination == "timeout":
            return f"[BLOCKED] Execution exceeded the {settings.sandbox_timeout_s}s wall-clock cap and was killed. The sandbox absorbed it."
        if result.termination == "oom":
            return "[BLOCKED] Execution exceeded the memory cap and was OOM-killed. The sandbox absorbed it."
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        clip = settings.tool_output_clip
        parts = []
        if out:
            parts.append(out[:clip] + (f"\n...[clipped {len(out) - clip} chars]" if len(out) > clip else ""))
        if result.exit_code != 0:
            parts.append(f"[exit {result.exit_code}] " + err[:clip])
        if result.artifacts:
            parts.append("Artifacts written: " + ", ".join(a["name"] for a in result.artifacts))
        return "\n".join(parts) or "(no output)"

    # -- main loop ---------------------------------------------------------
    def run_task(self, question: str, csv: tuple[str, bytes] | None = None, task_id: str | None = None) -> TaskOutcome:
        task_id = task_id or uuid.uuid4().hex[:12]
        receipt = Receipt(task_id=task_id)
        ws = WORKSPACES_DIR / task_id
        (ws / "input").mkdir(parents=True, exist_ok=True)
        (ws / "output").mkdir(parents=True, exist_ok=True)
        if csv:
            (ws / "input" / csv[0]).write_bytes(csv[1])
            receipt.add("DATA_SEALED", file=csv[0], bytes=len(csv[1]),
                        note="uploaded file mounted read-only into sandbox only")
        receipt.add("TASK_CREATED", task_id=task_id, question=question)

        outcome = TaskOutcome(task_id=task_id, question=question)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Question: {question}\n\n"
                f"Files available: {self._tool_list_files(ws)}\n"
                "Analyse the data and answer."
            )},
        ]

        try:
            for i in range(settings.max_agent_iterations):
                outcome.iterations = i + 1
                receipt.add("MODEL_CALL", iteration=i + 1)
                chat = self.client.chat(messages, tools=TOOLS_SCHEMA)
                outcome.model_used = chat.model
                receipt.add("MODEL_RESPONSE", model=chat.model,
                            finish_reason=chat.finish_reason, usage=chat.usage)

                if not chat.tool_calls:
                    outcome.answer = (chat.content or "").strip()
                    break

                messages.append({
                    "role": "assistant",
                    "content": chat.content,
                    "tool_calls": [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.name, "arguments": c.arguments}}
                        for c in chat.tool_calls
                    ],
                })
                for call in chat.tool_calls:
                    result = self._dispatch(call, ws, receipt, iteration=i + 1)
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": result})
            else:
                outcome.answer = "Analysis stopped at the iteration cap; see the receipt for everything that ran."

            outcome.artifacts = self._collect_artifacts(ws)
            receipt.add("TASK_COMPLETED", answer_chars=len(outcome.answer),
                        artifacts=[a["name"] for a in outcome.artifacts])
        except Exception as exc:  # noqa: BLE001 — a failed task must still seal its receipt
            outcome.status = "failed"
            outcome.error = str(exc)
            receipt.add("TASK_FAILED", error=str(exc)[:500])
        finally:
            path = receipt.finalize(
                question=question, model_used=outcome.model_used,
                iterations=outcome.iterations, status=outcome.status,
                workspace=str(ws),
            )
            outcome.receipt_path = str(path)

        return outcome

    def _dispatch(self, call: ToolCall, ws: Path, receipt: Receipt, iteration: int) -> str:
        receipt.add("TOOL_CALL", tool=call.name, iteration=iteration,
                    args_preview=call.arguments[:300])
        if call.name == "run_python":
            try:
                code = json.loads(call.arguments).get("code", "")
            except json.JSONDecodeError:
                return "[error] run_python arguments were not valid JSON."
            return self._tool_run_python(code, ws, receipt)
        if call.name == "list_files":
            return self._tool_list_files(ws)
        return f"[error] unknown tool {call.name}"

    @staticmethod
    def _collect_artifacts(ws: Path) -> list[dict[str, Any]]:
        out = ws / "output"
        return [
            {"name": p.name, "path": str(p), "size": p.stat().st_size}
            for p in sorted(out.iterdir())
            if p.is_file()
        ]
