"""Tamper-evident containment receipts.

Every task produces a receipt: an ordered event log where each event is chained to
the previous one with SHA-256. Anyone can re-verify the chain with `verify_receipt`.
This is the product: proof of what the agent did, what was blocked, and that the
sandbox was destroyed afterwards.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import RECEIPTS_DIR


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _now() -> float:
    return round(time.time(), 3)


@dataclass
class Receipt:
    task_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    _closed: bool = False

    def add(self, event_type: str, **detail: Any) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("receipt is closed")
        prev_hash = self.events[-1]["hash"] if self.events else "GENESIS"
        event = {
            "seq": len(self.events) + 1,
            "ts": _now(),
            "type": event_type,
            "detail": detail,
        }
        payload = _canonical({"prev": prev_hash, **event})
        event["prev_hash"] = prev_hash
        event["hash"] = hashlib.sha256(payload.encode()).hexdigest()
        self.events.append(event)
        return event

    def finalize(self, **summary: Any) -> Path:
        """Seal the receipt with a summary block and persist it."""
        self.add("RECEIPT_SEALED", **summary)
        self._closed = True
        doc = {
            "task_id": self.task_id,
            "algorithm": "sha256-chain",
            "secrets_injected_into_sandbox": "none",
            "events": self.events,
            "summary": summary,
        }
        path = RECEIPTS_DIR / f"{self.task_id}.json"
        path.write_text(json.dumps(doc, indent=2))
        return path

    def as_doc(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "algorithm": "sha256-chain", "events": self.events}


def verify_receipt(path: Path) -> dict[str, Any]:
    """Recompute the hash chain. Returns {'valid': bool, 'events': n, 'first_bad_seq': int|None}."""
    doc = json.loads(path.read_text())
    prev = "GENESIS"
    for ev in doc["events"]:
        body = {k: ev[k] for k in ("seq", "ts", "type", "detail")}
        payload = _canonical({"prev": prev, **body})
        if hashlib.sha256(payload.encode()).hexdigest() != ev.get("hash") or prev != ev.get("prev_hash"):
            return {"valid": False, "events": len(doc["events"]), "first_bad_seq": ev["seq"]}
        prev = ev["hash"]
    return {"valid": True, "events": len(doc["events"]), "first_bad_seq": None}
