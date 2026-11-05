"""Airlock configuration. All knobs come from the environment; sane defaults for demo."""
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("AIRLOCK_DATA_DIR", BASE_DIR / "data")).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
WORKSPACES_DIR = DATA_DIR / "workspaces"
RECEIPTS_DIR = DATA_DIR / "receipts"


def _load_dotenv() -> None:
    """Tiny .env loader (backend/.env) — no dependency, real env wins."""
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


def _ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, WORKSPACES_DIR, RECEIPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


@dataclass
class Settings:
    # --- Vultr Serverless Inference ---
    vultr_api_key: str = field(default_factory=lambda: os.environ.get("VULTR_INFERENCE_API_KEY", ""))
    inference_base_url: str = "https://api.vultrinference.com/v1"
    # Agent brain fallback chain (cheap flash models, $0.10/1M input tier).
    # Order matters: first that answers wins; per-model tool support is probed live.
    model_chain: list[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.environ.get(
                "AIRLOCK_MODEL_CHAIN",
                "glm-5.3-flash,qwen3.8-flash-next,mimo-v2.6-flash,nemotron-3-nano-omni-30b-a3b-reasoning",
            ).split(",")
            if m.strip()
        ]
    )
    # Vision-capable omni model (confirmed tool-calling support on Vultr).
    vision_model: str = os.environ.get("AIRLOCK_VISION_MODEL", "nemotron-3-nano-omni-30b-a3b-reasoning")
    request_timeout_s: float = float(os.environ.get("AIRLOCK_REQUEST_TIMEOUT_S", "180"))
    max_retries: int = int(os.environ.get("AIRLOCK_MAX_RETRIES", "3"))

    # --- Sandbox hard limits (per task) ---
    sandbox_image: str = os.environ.get("AIRLOCK_SANDBOX_IMAGE", "airlock-sandbox:latest")
    sandbox_mem: str = os.environ.get("AIRLOCK_SANDBOX_MEM", "256m")
    sandbox_cpus: str = os.environ.get("AIRLOCK_SANDBOX_CPUS", "0.5")
    sandbox_pids: int = int(os.environ.get("AIRLOCK_SANDBOX_PIDS", "64"))
    sandbox_timeout_s: int = int(os.environ.get("AIRLOCK_SANDBOX_TIMEOUT", "60"))
    sandbox_tmpfs: str = os.environ.get("AIRLOCK_SANDBOX_TMPFS", "/tmp:rw,noexec,nosuid,size=64m")

    # --- Agent loop ---
    max_agent_iterations: int = int(os.environ.get("AIRLOCK_MAX_ITERATIONS", "8"))
    tool_output_clip: int = int(os.environ.get("AIRLOCK_TOOL_OUTPUT_CLIP", "2000"))

    # --- App ---
    host: str = os.environ.get("AIRLOCK_HOST", "127.0.0.1")
    port: int = int(os.environ.get("AIRLOCK_PORT", "8000"))


def pick_sandbox_runtime() -> str:
    """gVisor (runsc) on Linux when available; default runtime elsewhere (e.g. macOS dev)."""
    forced = os.environ.get("AIRLOCK_SANDBOX_RUNTIME", "")
    if forced:
        return forced
    if platform.system() == "Linux" and shutil.which("runsc"):
        return "runsc"
    return "runc"


settings = Settings()
SANDBOX_RUNTIME = pick_sandbox_runtime()
