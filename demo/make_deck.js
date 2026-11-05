// Airlock demo deck — 6 slides, dark containment aesthetic matching the product.
const pptxgen = require("pptxgenjs");

const BG = "0B0F14", PANEL = "121A26", EDGE = "22303F";
const PRIMARY = "38E0B0", ACCENT = "F0B429";
const TEXT = "DCE7F2", MUTED = "8299AE";
const F = "Arial", MONO = "Courier New";
const W = 13.33, H = 7.5, M = 0.6;

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Airlock Team";
p.title = "Airlock — Agent Rush";

const shadow = () => ({ type: "outer", color: "000000", blur: 8, offset: 3, angle: 90, opacity: 0.35 });
const bu = () => ({ code: "25B8", indent: 12 });

function card(s, x, y, w, h) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, fill: { color: PANEL }, line: { color: EDGE, width: 1 },
    rectRadius: 0.08, shadow: shadow(),
  });
}
function tag(s, x, y, text, color) {
  const w = 0.16 + text.length * 0.085;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.34, fill: { color: PANEL }, line: { color, width: 1 }, rectRadius: 0.16 });
  s.addText(text, { x, y, w, h: 0.34, align: "center", valign: "middle", fontFace: MONO, fontSize: 10.5, color, margin: 0 });
}

// ---------- 1 · Title ----------
let s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "VULTR : AGENT RUSH — BLAST RADIUS ZERO", MUTED);
s.addText("AIRLOCK", { x: M, y: 1.7, w: 12, h: 1.5, fontFace: F, fontSize: 88, bold: true, color: PRIMARY, charSpacing: 4, margin: 0 });
s.addText([
  { text: "Sensitive-data analysis where the AI's code runs in a jail — ", options: { color: TEXT } },
  { text: "not on your servers.", options: { color: PRIMARY, bold: true } },
], { x: M, y: 3.35, w: 11.5, h: 1.0, fontFace: F, fontSize: 28, margin: 0 });
card(s, M, 4.9, 12.13, 1.7);
s.addText([
  { text: "An LLM writes pandas code. That code executes inside a sealed, network-isolated gVisor sandbox on a Vultr VM. ", options: { color: MUTED } },
  { text: "Every task ends with a tamper-evident containment receipt.", options: { color: TEXT, bold: true } },
], { x: M + 0.35, y: 5.05, w: 11.4, h: 1.4, fontFace: F, fontSize: 17, margin: 0 });
s.addText("Team solo  ·  Python · FastAPI · Docker + gVisor · Vultr Serverless Inference", { x: M, y: 6.85, w: 12, h: 0.4, fontFace: F, fontSize: 13, color: MUTED, margin: 0 });

// ---------- 2 · Problem ----------
s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "THE PROBLEM", MUTED);
s.addText([
  { text: "Trust — not capability — is the blocker.", options: { color: TEXT } },
], { x: M, y: 1.0, w: 12, h: 0.9, fontFace: F, fontSize: 40, bold: true, margin: 0 });
s.addText("Companies want analyst-grade AI productivity. They cannot hand model-generated code their customer data, because the code can do this:", { x: M, y: 2.0, w: 11.8, h: 0.75, fontFace: F, fontSize: 18, color: MUTED, margin: 0 });
const threats = [
  ["rm -rf /", "an LLM code-interpreter error destroys the workstation it runs on"],
  ["exfiltrate", "the dataset leaves for an endpoint nobody approved — silently"],
  ["fork bomb / zip bomb", "one prompt away from taking the host down"],
  ["no audit trail", "'what exactly did the AI run?' has no answer"],
];
threats.forEach((t, i) => {
  const y = 3.0 + i * 0.92;
  card(s, M, y, 12.13, 0.72);
  s.addText(t[0], { x: M + 0.3, y, w: 3.2, h: 0.72, fontFace: MONO, fontSize: 16, bold: true, color: ACCENT, valign: "middle", margin: 0 });
  s.addText(t[1], { x: M + 3.8, y, w: 8.0, h: 0.72, fontFace: F, fontSize: 15, color: TEXT, valign: "middle", margin: 0 });
});
s.addText("Existing options: SaaS interpreters are black boxes on someone else's cloud; DIY Docker is unaudited. Neither gives proof.", { x: M, y: 6.85, w: 12, h: 0.5, fontFace: F, fontSize: 13, italic: true, color: MUTED, margin: 0 });

// ---------- 3 · Architecture ----------
s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "ARCHITECTURE — ONE VULTR VM", MUTED);
s.addText("One Vultr VM: the jail, the brain, the control plane", { x: M, y: 1.2, w: 12, h: 0.55, fontFace: F, fontSize: 30, bold: true, color: TEXT, margin: 0 });

// browser
card(s, 0.7, 2.4, 2.4, 1.5);
s.addText("Browser", { x: 0.7, y: 2.75, w: 2.4, h: 0.5, align: "center", fontFace: F, fontSize: 18, bold: true, color: TEXT, margin: 0 });
s.addText("upload · question", { x: 0.7, y: 3.25, w: 2.4, h: 0.4, align: "center", fontFace: F, fontSize: 12, color: MUTED, margin: 0 });
// VM
card(s, 4.0, 1.95, 5.1, 4.45);
s.addText("VULTR VM — control plane", { x: 4.2, y: 2.12, w: 4.7, h: 0.45, fontFace: F, fontSize: 16, bold: true, color: PRIMARY, margin: 0 });
s.addText("FastAPI app · agent loop · receipts (sha256 chain)", { x: 4.2, y: 2.58, w: 4.7, h: 0.6, fontFace: F, fontSize: 13, color: MUTED, margin: 0 });
card(s, 4.35, 3.3, 4.4, 2.9);
s.addText("SANDBOX — per task", { x: 4.55, y: 3.46, w: 4.0, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: TEXT, margin: 0 });
s.addText([
  { text: "gVisor (runsc) userspace kernel", options: { bullet: bu(), breakLine: true, color: TEXT } },
  { text: "network: none — no internet, no API", options: { bullet: bu(), breakLine: true, color: TEXT } },
  { text: "256 MB · 0.5 CPU · 64 pids · 60 s cap", options: { bullet: bu(), breakLine: true, color: TEXT } },
  { text: "read-only rootfs · caps dropped", options: { bullet: bu(), breakLine: true, color: TEXT } },
  { text: "destroyed in a finally block", options: { bullet: bu(), color: TEXT } },
], { x: 4.55, y: 3.75, w: 4.05, h: 2.1, fontFace: F, fontSize: 13, paraSpaceAfter: 6, margin: 0 });
// inference
card(s, 10.1, 2.4, 2.6, 1.9);
s.addText("Vultr Serverless Inference", { x: 10.2, y: 2.62, w: 2.4, h: 0.7, align: "center", fontFace: F, fontSize: 15, bold: true, color: TEXT, margin: 0 });
s.addText("api.vultrinference.com/v1\nALL LLM calls · tools[]", { x: 10.2, y: 3.35, w: 2.4, h: 0.8, align: "center", fontFace: MONO, fontSize: 10.5, color: MUTED, margin: 0 });
// connectors
s.addShape(p.shapes.LINE, { x: 3.1, y: 3.15, w: 0.9, h: 0, line: { color: PRIMARY, width: 2.5, endArrowType: "triangle" } });
s.addShape(p.shapes.LINE, { x: 9.1, y: 3.35, w: 1.0, h: 0, line: { color: PRIMARY, width: 2.5, endArrowType: "triangle" } });
s.addText("HTTPS", { x: 2.95, y: 2.75, w: 1.2, h: 0.3, align: "center", fontFace: MONO, fontSize: 10, color: MUTED, margin: 0 });
s.addText("only egress", { x: 8.95, y: 2.95, w: 1.3, h: 0.3, align: "center", fontFace: MONO, fontSize: 10, color: MUTED, margin: 0 });
s.addText("The sandbox has no network at all — the model's only influence on execution is the code it writes.", { x: M, y: 6.75, w: 12, h: 0.5, fontFace: F, fontSize: 13, italic: true, color: MUTED, margin: 0 });

// ---------- 4 · Receipt ----------
s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "PROOF, NOT PROMISES", MUTED);
s.addText("Every task seals a tamper-evident containment receipt", { x: M, y: 0.95, w: 12, h: 0.65, fontFace: F, fontSize: 30, bold: true, color: TEXT, margin: 0 });
const guarantees = [
  ["Process isolation", "fresh container per run; gVisor intercepts every syscall"],
  ["Secret hygiene", "zero credentials in the sandbox — the API key never enters"],
  ["Resource limits", "memory / CPU / pids / wall-clock caps on every execution"],
  ["Lifecycle discipline", "force-removed in finally — nothing survives the task"],
];
guarantees.forEach((g, i) => {
  const y = 2.0 + i * 1.12;
  s.addText(g[0], { x: M, y, w: 5.6, h: 0.5, fontFace: F, fontSize: 19, bold: true, color: PRIMARY, margin: 0 });
  s.addText(g[1], { x: M, y: y + 0.45, w: 5.6, h: 0.55, fontFace: F, fontSize: 14, color: MUTED, margin: 0 });
  if (i < 3) s.addShape(p.shapes.LINE, { x: M, y: y + 1.0, w: 5.4, h: 0, line: { color: EDGE, width: 0.75 } });
});
card(s, 7.0, 1.9, 5.7, 4.7);
s.addText("receipt · task 3b97d5b4c9a8 · chain verified", { x: 7.25, y: 2.1, w: 5.2, h: 0.4, fontFace: MONO, fontSize: 12, color: PRIMARY, margin: 0 });
s.addText([
  { text: "01  TASK_CREATED          question, mode", options: { breakLine: true } },
  { text: "02  DATA_SEALED           data.csv · read-only", options: { breakLine: true } },
  { text: "03  SANDBOX_CREATED       network=none limits", options: { breakLine: true } },
  { text: "04  MODEL_CALL            iteration 1", options: { breakLine: true } },
  { text: "05  MODEL_RESPONSE        finish=tool_calls", options: { breakLine: true } },
  { text: "06  TOOL_CALL             run_python()", options: { breakLine: true } },
  { text: "07  SANDBOX_DESTROYED     removed=true", options: { breakLine: true } },
  { text: "08  TASK_COMPLETED        artifacts: 1", options: { breakLine: true } },
  { text: "09  RECEIPT_SEALED        sha256 chain ✓", options: {} },
], { x: 7.25, y: 2.55, w: 5.2, h: 3.3, fontFace: MONO, fontSize: 11, color: TEXT, paraSpaceAfter: 4, margin: 0 });
s.addText("SHA-256 chained: edit one event and verification fails on screen.", { x: 7.25, y: 6.05, w: 5.2, h: 0.5, fontFace: F, fontSize: 12.5, italic: true, color: MUTED, margin: 0 });

// ---------- 5 · Attack mode ----------
s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "ATTACK MODE — THE CONTAINMENT MOMENT", MUTED);
s.addText([
  { text: "5 / 5 ", options: { color: PRIMARY, fontSize: 66, bold: true } },
  { text: "payloads absorbed", options: { color: TEXT, fontSize: 34, bold: true } },
], { x: M, y: 0.95, w: 12, h: 1.15, fontFace: F, margin: 0 });
const rows = [
  ["rm -rf /", "read-only rootfs + dropped capabilities", "Errno 30: Read-only file system"],
  ["fork bomb", "pids cap", "EAGAIN after 64 forks"],
  ["memory bomb", "cgroup memory cap", "kernel OOM-kill (exit 137)"],
  ["exfiltration", "network: none", "URLError: no route to host"],
  ["zip bomb (2 GB)", "memory cap", "OOM-killed mid-decompress"],
];
rows.forEach((r, i) => {
  const y = 2.35 + i * 0.78;
  card(s, M, y, 12.13, 0.62);
  s.addText(r[0], { x: M + 0.28, y, w: 2.9, h: 0.62, fontFace: MONO, fontSize: 13.5, bold: true, color: TEXT, valign: "middle", margin: 0 });
  s.addText(r[1], { x: M + 3.35, y, w: 4.3, h: 0.62, fontFace: F, fontSize: 13, color: MUTED, valign: "middle", margin: 0 });
  s.addText(r[2], { x: M + 7.7, y, w: 2.9, h: 0.62, fontFace: MONO, fontSize: 11, color: MUTED, valign: "middle", margin: 0 });
  s.addText("ABSORBED", { x: M + 10.7, y, w: 1.25, h: 0.62, fontFace: F, fontSize: 12, bold: true, color: PRIMARY, valign: "middle", margin: 0 });
});
s.addText("Nothing is special-cased: attacks run through the same jailed pipeline as a normal analysis — then the service is health-checked on camera.", { x: M, y: 6.55, w: 12, h: 0.7, fontFace: F, fontSize: 13.5, italic: true, color: MUTED, margin: 0 });

// ---------- 6 · Why it matters ----------
s = p.addSlide();
s.background = { color: BG };
tag(s, M, 0.55, "WHY IT MATTERS", MUTED);
s.addText([
  { text: "The agent is disposable. ", options: { color: MUTED } },
  { text: "Your data and infrastructure are not.", options: { color: TEXT } },
], { x: M, y: 1.0, w: 12.2, h: 0.85, fontFace: F, fontSize: 34, bold: true, margin: 0 });
const cols = [
  ["For the analyst", ["Plain-English questions over sensitive CSVs", "Executed code, not hallucinated numbers", "Charts + code + answer in one pass"]],
  ["For the CISO", ["Proof of what the AI did — and what it couldn't", "Data never leaves your Vultr VM", "Every run ends with a destroyed sandbox"]],
  ["For the business", ["Unblocks AI adoption in regulated work", "Self-hosted: one VM, no per-seat SaaS", "Audit-ready receipts for compliance"]],
];
cols.forEach((c, i) => {
  const x = M + i * 4.18;
  card(s, x, 2.2, 3.9, 3.4);
  s.addText(c[0], { x: x + 0.25, y: 2.4, w: 3.4, h: 0.5, fontFace: F, fontSize: 17, bold: true, color: PRIMARY, margin: 0 });
  s.addText(c[1].map((t, j) => ({ text: t, options: { bullet: bu(), breakLine: j < c[1].length - 1 } })),
    { x: x + 0.25, y: 3.0, w: 3.45, h: 2.4, fontFace: F, fontSize: 13.5, color: TEXT, paraSpaceAfter: 8, margin: 0 });
});
s.addText("Data in. Code jailed. Results out. Receipt sealed.", { x: M, y: 6.1, w: 12, h: 0.55, fontFace: F, fontSize: 20, bold: true, color: TEXT, margin: 0 });
s.addText("Airlock · MIT · runs on any Vultr VM", { x: M, y: 6.8, w: 12, h: 0.4, fontFace: F, fontSize: 12.5, color: MUTED, margin: 0 });

p.writeFile({ fileName: "/Users/efi/Hackathons/Agent Rush/airlock/demo/airlock-slides.pptx" })
  .then(() => console.log("deck written"));
