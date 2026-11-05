"""Submission cover image (1280x720) styled like the product UI."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG, PANEL, EDGE = "#0b0f14", "#121a26", "#22303f"
PRIMARY, ACCENT, TEXT, MUTED = "#38e0b0", "#f0b429", "#dce7f2", "#8299ae"

fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1280)
ax.set_ylim(0, 720)
ax.axis("off")
fig.patch.set_facecolor(BG)

# receipt card motif on the right
rx, ry, rw, rh = 830, 120, 380, 480
ax.add_patch(plt.Rectangle((rx, ry), rw, rh, facecolor=PANEL, edgecolor=EDGE, lw=1.5, zorder=2))
events = [
    ("01", "TASK_CREATED", "question"),
    ("02", "DATA_SEALED", "read-only"),
    ("03", "SANDBOX_CREATED", "net=none"),
    ("04", "MODEL_CALL", "iter 1"),
    ("05", "TOOL_CALL", "run_python()"),
    ("06", "SANDBOX_DESTROYED", "removed"),
    ("07", "TASK_COMPLETED", "artifacts"),
    ("08", "RECEIPT_SEALED", "sha256"),
]
ax.text(rx + 24, ry + rh - 44, "receipt · chain verified", family="monospace",
        fontsize=11.5, color=PRIMARY, zorder=3)
for i, (seq, ev, det) in enumerate(events):
    y = ry + rh - 95 - i * 44
    ax.text(rx + 24, y, seq, family="monospace", fontsize=10.5, color=MUTED, zorder=3)
    ax.text(rx + 62, y, ev, family="monospace", fontsize=10.5, color=TEXT, zorder=3)
    ax.text(rx + 62, y - 17, det, family="monospace", fontsize=9, color=MUTED, zorder=3)
ax.plot([rx + 24, rx + rw - 24], [ry + 34, ry + 34], color=PRIMARY, lw=1, zorder=3)
ax.text(rx + 24, ry + 14, "tamper-evident · sha256 chain", family="monospace",
        fontsize=9, color=PRIMARY, zorder=3)

# left: identity
ax.text(80, 560, "A I R L O C K", fontsize=58, fontweight="bold", color=PRIMARY, zorder=3)
ax.text(80, 470, "Sensitive-data analysis where the AI's code", fontsize=20, color=TEXT, zorder=3)
ax.text(80, 438, "runs in a jail — not on your servers.", fontsize=20, color=TEXT, zorder=3)
ax.text(80, 372, "Every action contained in a sandbox on Vultr.", fontsize=14, color=MUTED, zorder=3)
ax.text(80, 348, "Every task sealed with a tamper-evident receipt.", fontsize=14, color=MUTED, zorder=3)

chips = ["Vultr VM", "gVisor sandbox", "Serverless Inference", "network: none"]
x = 80
for c in chips:
    w = 24 + len(c) * 8.4
    ax.add_patch(plt.Rectangle((x, 280), w, 40, facecolor=PANEL, edgecolor=EDGE, lw=1.2, zorder=3))
    ax.text(x + w / 2, 293, c, fontsize=11, color=PRIMARY, ha="center", family="monospace", zorder=4)
    x += w + 14

ax.text(80, 150, "VULTR : AGENT RUSH HACKATHON — BLAST RADIUS ZERO", fontsize=12,
        family="monospace", color=MUTED, zorder=3)

fig.savefig("/Users/efi/Hackathons/Agent Rush/airlock/demo/cover.png", facecolor=BG)
print("cover written")
