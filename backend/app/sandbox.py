"""Sandbox manager: one disposable Docker container per execution.

Hardening (maps 1:1 to the four containment requirements in the challenge):
  * process isolation  -> separate container, never the app process; gVisor (runsc)
                          on Linux when available (userspace kernel, no host syscalls)
  * secret hygiene     -> no env, no volumes besides the task workspace, API key never passed
  * resource limits    -> memory / cpu / pids caps + wall-clock timeout + read-only rootfs
  * lifecycle          -> container is force-removed in `finally`; nothing survives the task
"""
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import (
    SANDBOX_RUNTIME,
    WORKSPACES_DIR,
    settings,
)

Event = Callable[[str, dict[str, Any]], None]


@dataclass
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    termination: str = "completed"  # completed | timeout | oom | error
    task_id: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def _docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )


def docker_available() -> bool:
    try:
        return _docker("info", "--format", "ok", timeout=10).stdout.strip() == "ok"
    except Exception:
        return False


def _looks_like_oom(stderr: str, exit_code: int | None) -> bool:
    markers = ("MemoryError", "Killed", "OOMKilled", "Cannot allocate memory", "std::bad_alloc")
    if exit_code == 137:  # 128+SIGKILL: the kernel OOM-killed the cgroup before python could raise
        return True
    return exit_code not in (0, None) and any(m in stderr for m in markers)


class Sandbox:
    """Runs one python job inside a hardened throwaway container."""

    def __init__(self, on_event: Event | None = None):
        self.on_event = on_event or (lambda t, d: None)

    def _emit(self, event_type: str, **detail: Any) -> None:
        self.on_event(event_type, detail)

    def run(
        self,
        code: str,
        *,
        input_files: dict[str, bytes] | None = None,
        timeout: int | None = None,
        workspace: Path | None = None,
    ) -> SandboxResult:
        """Execute `code` in a fresh hardened container.

        `workspace` (optional) lets an agent task reuse one /work across multiple
        container lifecycles: containers are still created and destroyed per run;
        only the host-side workspace persists. If omitted, a throwaway workspace
        is created (and its id returned in the result).
        """
        task_id = uuid.uuid4().hex[:12]
        ws = workspace or (WORKSPACES_DIR / task_id)
        (ws / "input").mkdir(parents=True, exist_ok=True)
        (ws / "output").mkdir(parents=True, exist_ok=True)
        (ws / "job.py").write_text(code)
        if workspace is None:
            for name, blob in (input_files or {}).items():
                (ws / "input" / name).write_bytes(blob)

        timeout = timeout or settings.sandbox_timeout_s
        container = f"airlock-{task_id}"
        cmd = [
            "docker", "run",
            "--name", container,
            "--rm",
            "--runtime", SANDBOX_RUNTIME,
            "--network", "none",
            "--memory", settings.sandbox_mem,
            "--cpus", settings.sandbox_cpus,
            "--pids-limit", str(settings.sandbox_pids),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", settings.sandbox_tmpfs,
            "--user", "65534:65534",
            "--env", "MPLCONFIGDIR=/tmp/mpl",
            "--env", "HOME=/tmp",
            "-v", f"{ws / 'job.py'}:/work/job.py:ro",
            "-v", f"{ws / 'input'}:/work/input:ro",
            "-v", f"{ws / 'output'}:/work/output:rw",
            settings.sandbox_image,
            "python3", "/work/job.py",
        ]

        self._emit("SANDBOX_CREATED", task_id=task_id, runtime=SANDBOX_RUNTIME,
                   limits={"mem": settings.sandbox_mem, "cpus": settings.sandbox_cpus,
                           "pids": settings.sandbox_pids, "timeout_s": timeout},
                   network="none")
        start = time.monotonic()
        termination = "completed"
        exit_code: int | None = None
        stdout = stderr = ""
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
            if _looks_like_oom(stderr, exit_code):
                termination = "oom"
        except subprocess.TimeoutExpired as exc:
            termination = "timeout"
            stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        finally:
            # lifecycle discipline: the container never outlives this call
            if termination == "timeout":
                _docker("kill", container, timeout=30)
                self._emit("BLOCKED_TIMEOUT", task_id=task_id, timeout_s=timeout)
            removed = _docker("rm", "-f", container, timeout=30)
            self._emit(
                "SANDBOX_DESTROYED", task_id=task_id,
                removed=(removed.returncode == 0),
                duration_s=round(time.monotonic() - start, 2),
            )

        duration = round(time.monotonic() - start, 2)
        if termination == "oom":
            self._emit("BLOCKED_OOM", task_id=task_id, hint=stderr[-300:])
        artifacts = []
        out_dir = ws / "output"
        for p in sorted(out_dir.rglob("*")):
            if p.is_file():
                artifacts.append({"name": str(p.relative_to(out_dir)), "size": p.stat().st_size,
                                  "path": str(p)})
        if artifacts:
            self._emit("ARTIFACTS", task_id=task_id, files=[a["name"] for a in artifacts])

        return SandboxResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr, artifacts=artifacts,
            duration_s=duration, termination=termination, task_id=task_id,
        )

    @staticmethod
    def read_artifact(path: str | Path) -> bytes:
        return Path(path).read_bytes()

    @staticmethod
    def cleanup_workspace(task_id: str) -> None:
        shutil.rmtree(WORKSPACES_DIR / task_id, ignore_errors=True)


def build_sandbox_image() -> bool:
    """Build the hardened sandbox image (idempotent)."""
    root = Path(__file__).resolve().parent.parent.parent  # airlock/
    proc = subprocess.run(
        ["docker", "build", "-t", settings.sandbox_image, str(root / "sandbox-image")],
        capture_output=True, text=True,
    )
    return proc.returncode == 0
