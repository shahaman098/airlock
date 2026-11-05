"""Hello-sandbox gate: prove containment end-to-end before anything else gets built.

Run: .venv/bin/python tests/gate_sandbox.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.receipts import Receipt, verify_receipt  # noqa: E402
from app.sandbox import Sandbox, docker_available  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name}{': ' + detail if detail else ''}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main() -> None:
    assert docker_available(), "docker daemon not reachable"
    sb = Sandbox()
    csv = (
        b"region,units,revenue\nnorth,120,4800\nsouth,80,3100\n"
        b"east,150,5900\nwest,95,3700\n"
    )

    # 1. analysis job: read mounted CSV, write a chart artifact
    r = sb.run(
        "import pandas as pd, matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "df = pd.read_csv('/work/input/demo.csv')\n"
        "print(df.groupby('region')['revenue'].sum().to_string())\n"
        "df.plot.bar(x='region', y='revenue', legend=False)\n"
        "plt.tight_layout(); plt.savefig('/work/output/chart.png')\n"
        "print('done')\n",
        input_files={"demo.csv": csv},
    )
    check("analysis job exits 0", r.ok, f"exit={r.exit_code} err={r.stderr[-200:]}")
    check("stdout has totals", "east" in r.stdout)
    check("chart artifact produced", any(a["name"] == "chart.png" for a in r.artifacts))

    # 2. infinite loop -> absorbed by wall-clock cap
    t0 = time.monotonic()
    r = sb.run("while True: pass", input_files={"demo.csv": csv}, timeout=6)
    check("infinite loop absorbed", r.termination == "timeout", f"term={r.termination}")
    check("timeout enforced quickly", time.monotonic() - t0 < 30)

    # 3. rm -rf -> host intact, blocked by read-only rootfs + dropped caps
    r = sb.run(
        "import shutil\n"
        "for t in ['/', '/usr', '/etc']:\n"
        "    try:\n"
        "        shutil.rmtree(t)\n"
        "        print(f'deleted {t}')\n"
        "    except Exception as e:\n"
        "        print(f'BLOCKED {t}: {type(e).__name__}')\n",
        input_files={"demo.csv": csv},
    )
    check("rm -rf attempt blocked", "BLOCKED /" in r.stdout and r.termination == "completed",
          r.stdout[-200:])

    # 4. no network -> exfil impossible
    r = sb.run(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=4)\n"
        "    print('NETWORK REACHED (bad)')\n"
        "except Exception as e:\n"
        "    print(f'BLOCKED: {type(e).__name__}')\n",
        input_files={"demo.csv": csv},
    )
    check("network isolation holds", "BLOCKED" in r.stdout and "NETWORK REACHED" not in r.stdout,
          r.stdout[-120:])

    # 5. memory bomb -> OOM path detected
    r = sb.run(
        "chunks=[]\n"
        "try:\n"
        "    while True:\n"
        "        chunks.append(bytearray(10*1024*1024))\n"
        "except MemoryError:\n"
        "    print('blocked at python level')\n",
        input_files={"demo.csv": csv},
    )
    check("memory bomb absorbed",
          r.termination == "oom" or (r.termination == "completed" and "blocked" in r.stdout.lower()),
          f"term={r.termination}")

    # 6. lifecycle: nothing left running
    import subprocess
    leftovers = subprocess.run(
        ["docker", "ps", "--filter", "name=airlock-", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    ).stdout.strip()
    check("no containers survive", leftovers == "", leftovers)

    # 7. receipt hash chain round-trip
    rc = Receipt(task_id="gatetest")
    rc.add("SANDBOX_CREATED", runtime="runc")
    rc.add("CODE_EXECUTED", exit_code=0)
    rc.add("SANDBOX_DESTROYED", removed=True)
    path = rc.finalize(status="completed")
    verdict = verify_receipt(path)
    check("receipt chain verifies", verdict["valid"], str(verdict))
    tampered = json.loads(path.read_text())
    tampered["events"][1]["detail"]["exit_code"] = 1
    path.write_text(json.dumps(tampered))
    check("tampering detected", verify_receipt(path)["valid"] is False)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
