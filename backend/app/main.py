"""Airlock web app: workbench, live run timeline (SSE), attack mode, receipts."""
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import attacks
from .agent import AirlockAgent, TaskOutcome
from .config import RECEIPTS_DIR, SANDBOX_RUNTIME, UPLOADS_DIR, WORKSPACES_DIR, settings
from .receipts import Receipt, verify_receipt
from .sandbox import Sandbox, docker_available
from .vultr_client import VultrClient

MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="Airlock")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")

_client: VultrClient | None = None
_client_lock = threading.Lock()


def get_client() -> VultrClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = VultrClient()
        return _client


@dataclass
class Run:
    id: str
    kind: str  # "task" | "attack"
    title: str
    status: str = "running"  # running | completed | failed
    events: list[dict[str, Any]] = field(default_factory=list)
    outcome: TaskOutcome | None = None
    attack_result: dict[str, Any] | None = None
    health_after: dict[str, Any] | None = None


RUNS: dict[str, Run] = {}
RUNS_LOCK = threading.Lock()


def record_event(run_id: str, event_type: str, detail: dict[str, Any]) -> None:
    with RUNS_LOCK:
        run = RUNS.get(run_id)
        if run is not None:
            run.events.append({"type": event_type, **detail})


# ---------------------------------------------------------------------------
# background runners
# ---------------------------------------------------------------------------

class FakeAgent:
    """Deterministic agent used when VULTR_INFERENCE_API_KEY is absent (UI development).

    Exercises the exact same sandbox, receipts and SSE paths as the real agent —
    only the model call is replaced.
    """

    model_used = "fake-model (set VULTR_INFERENCE_API_KEY for real analysis)"

    def __init__(self, on_event=None):
        self.on_event = on_event or (lambda t, d: None)

    def run_task(self, question: str, csv: tuple[str, bytes] | None = None, task_id: str | None = None) -> TaskOutcome:
        outcome = TaskOutcome(task_id=task_id or uuid.uuid4().hex[:12], question=question)
        receipt = Receipt(task_id=outcome.task_id)

        def ev(t: str, **d: Any) -> None:
            receipt.add(t, **d)
            self.on_event(t, d)

        ws = WORKSPACES_DIR / outcome.task_id
        ev("TASK_CREATED", question=question, mode="fake")
        if csv:
            (ws / "input").mkdir(parents=True, exist_ok=True)
            (ws / "input" / csv[0]).write_bytes(csv[1])
            ev("DATA_SEALED", file=csv[0], bytes=len(csv[1]), note="read-only in sandbox")

        fname = csv[0] if csv else "missing.csv"
        code = (
            "import pandas as pd\n"
            f"df = pd.read_csv('/work/input/{fname}')\n"
            "print(df.describe().to_string())\n"
            "print('rows:', len(df), 'cols:', list(df.columns))\n"
        )
        sb = Sandbox(on_event=lambda t, d: ev(t, **d))
        result = sb.run(code, workspace=ws)
        outcome.answer = (
            "Demo mode (no inference key configured). The sandbox executed a summary of your file:\n\n"
            + (result.stdout or result.stderr or "(no output)")
        )
        out_dir = ws / "output"
        if out_dir.exists():
            outcome.artifacts = [
                {"name": p.name, "path": str(p), "size": p.stat().st_size}
                for p in sorted(out_dir.iterdir()) if p.is_file()
            ]
        receipt.add("TASK_COMPLETED", mode="fake")
        path = receipt.finalize(question=question, model_used=self.model_used, status="completed")
        outcome.receipt_path = str(path)
        outcome.model_used = self.model_used
        return outcome


def _run_task_bg(run_id: str, question: str, csv: tuple[str, bytes] | None, fake: bool) -> None:
    try:
        agent: Any
        if fake:
            agent = FakeAgent(on_event=lambda t, d: record_event(run_id, t, d))
        else:
            agent = AirlockAgent(get_client(), on_event=lambda t, d: record_event(run_id, t, d))
        outcome = agent.run_task(question, csv, task_id=run_id)
        # normalise receipt path -> run id for serving
        with RUNS_LOCK:
            run = RUNS[run_id]
            run.outcome = outcome
            run.status = outcome.status
    except Exception as exc:  # noqa: BLE001
        record_event(run_id, "RUN_FAILED", {"error": str(exc)[:300]})
        with RUNS_LOCK:
            RUNS[run_id].status = "failed"


def _run_attack_bg(run_id: str, key: str) -> None:
    payload = attacks.PAYLOADS[key]
    receipt = Receipt(task_id=run_id)

    def ev(t: str, **d: Any) -> None:
        receipt.add(t, **d)
        record_event(run_id, t, d)

    try:
        ev("ATTACK_STARTED", payload=key, label=payload["label"])
        sb = Sandbox(on_event=lambda t, d: ev(t, **d))
        result = sb.run(payload["code"], timeout=30)
        absorbed = (
            (result.termination in ("timeout", "oom"))
            or (result.termination == "completed" and result.ok and "BLOCKED" in result.stdout)
        )
        ev("ATTACK_VERDICT", absorbed=absorbed, termination=result.termination,
           exit_code=result.exit_code, stdout_tail=result.stdout[-400:])
        health = {
            "status": "ok",
            "docker": docker_available(),
            "runtime": SANDBOX_RUNTIME,
        }
        ev("SERVICE_HEALTH_AFTER", **health)
        path = receipt.finalize(payload=key, absorbed=absorbed, service_healthy=True)
        with RUNS_LOCK:
            run = RUNS[run_id]
            run.attack_result = {
                "absorbed": absorbed, "termination": result.termination,
                "stdout": result.stdout[-1500:], "stderr": result.stderr[-400:],
                "exit_code": result.exit_code, "health": health,
                "receipt": f"/receipt/{run_id}",
            }
            run.status = "completed" if absorbed else "failed"
    except Exception as exc:  # noqa: BLE001
        record_event(run_id, "RUN_FAILED", error=str(exc)[:300])
        with RUNS_LOCK:
            RUNS[run_id].status = "failed"


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    recent = []
    for p in sorted(RECEIPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
        doc = json.loads(p.read_text())
        recent.append({"id": p.stem, "summary": doc.get("summary", {}), "valid": verify_receipt(p)})
    return templates.TemplateResponse(request, "workbench.html", {
        "recent": recent,
        "api_key_set": bool(settings.vultr_api_key),
        "runtime": SANDBOX_RUNTIME,
        "docker_ok": docker_available(),
    })


@app.post("/upload")
def upload(request: Request, file: bytes = File(...), question: str = Form(...)):
    if len(file) > MAX_UPLOAD:
        raise HTTPException(413, "file exceeds the 10 MB workbench cap")
    name = "data.csv"
    run_id = uuid.uuid4().hex[:12]
    (UPLOADS_DIR / run_id).mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / run_id / name).write_bytes(file)
    with RUNS_LOCK:
        RUNS[run_id] = Run(id=run_id, kind="task", title=question)
    fake = not settings.vultr_api_key
    threading.Thread(target=_run_task_bg, args=(run_id, question, (name, file), fake), daemon=True).start()
    return templates.TemplateResponse(request, "redirect.html", {"url": f"/run/{run_id}"})


@app.get("/run/{run_id}", response_class=HTMLResponse)
def run_page(request: Request, run_id: str):
    with RUNS_LOCK:
        run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    return templates.TemplateResponse(request, "run.html", {
        "run": run, "is_attack": run.kind == "attack",
        "payloads": attacks.PAYLOADS if run.kind == "attack" else None,
        "api_key_set": bool(settings.vultr_api_key),
    })


@app.get("/events/{run_id}")
def events(run_id: str):
    terminal = {"TASK_COMPLETED", "TASK_FAILED", "RUN_FAILED", "ATTACK_VERDICT"}

    def stream():
        cursor = 0
        for _ in range(1500):  # hard stop ~10 min
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                if run is None:
                    yield "event: gone\ndata: {}\n\n"
                    return
                batch = run.events[cursor:]
                cursor = len(run.events)
                status = run.status
            for ev in batch:
                yield f"data: {json.dumps(ev)}\n\n"
            if any(e.get("type") in terminal for e in batch) or status != "running":
                yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                return
            yield ": keepalive\n\n"
            time.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/run/{run_id}/result", response_class=HTMLResponse)
def run_result(request: Request, run_id: str):
    with RUNS_LOCK:
        run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    return templates.TemplateResponse(request, "_result.html", {"run": run})


@app.get("/artifact/{run_id}/{name}")
def artifact(run_id: str, name: str):
    p = WORKSPACES_DIR / run_id / "output" / Path(name).name
    if not p.is_file():
        raise HTTPException(404)
    media = "image/png" if p.suffix == ".png" else "application/octet-stream"
    return StreamingResponse(open(p, "rb"), media_type=media)


@app.get("/attack", response_class=HTMLResponse)
def attack_page(request: Request):
    return templates.TemplateResponse(request, "attack.html", {
        "payloads": attacks.PAYLOADS, "runtime": SANDBOX_RUNTIME,
        "docker_ok": docker_available(),
    })


@app.post("/attack/{key}", response_class=HTMLResponse)
def attack_run(request: Request, key: str):
    if key not in attacks.PAYLOADS:
        raise HTTPException(404, "unknown payload")
    run_id = uuid.uuid4().hex[:12]
    with RUNS_LOCK:
        RUNS[run_id] = Run(id=run_id, kind="attack", title=attacks.PAYLOADS[key]["label"])
    threading.Thread(target=_run_attack_bg, args=(run_id, key), daemon=True).start()
    return templates.TemplateResponse(request, "redirect.html", {"url": f"/run/{run_id}"})


@app.get("/receipt/{run_id}", response_class=HTMLResponse)
def receipt_view(request: Request, run_id: str):
    path = RECEIPTS_DIR / f"{run_id}.json"
    if not path.is_file():
        raise HTTPException(404, "receipt not found")
    doc = json.loads(path.read_text())
    return templates.TemplateResponse(request, "receipt.html", {
        "doc": doc, "verify": verify_receipt(path), "raw": json.dumps(doc, indent=2),
    })


@app.get("/receipts", response_class=HTMLResponse)
def receipts(request: Request):
    rows = []
    for p in sorted(RECEIPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        doc = json.loads(p.read_text())
        rows.append({"id": p.stem, "summary": doc.get("summary", {}),
                     "question": doc.get("summary", {}).get("question", ""),
                     "valid": verify_receipt(p)})
    return templates.TemplateResponse(request, "receipts.html", {"rows": rows})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "docker": docker_available(),
        "sandbox_runtime": SANDBOX_RUNTIME,
        "inference_configured": bool(settings.vultr_api_key),
        "model_chain": settings.model_chain,
        "sandbox_image": settings.sandbox_image,
        "limits": {"mem": settings.sandbox_mem, "cpus": settings.sandbox_cpus,
                   "pids": settings.sandbox_pids, "timeout_s": settings.sandbox_timeout_s},
    }
