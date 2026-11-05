# Airlock Demo Video Script (target 3:30–4:00)

Recording plan: screen capture at 1440p, browser only (no terminal except Scene 4's
`docker ps` proof — 15s max, font size 18+). Captions on. Rehearse twice against the
clock. The containment moment is the centrepiece — do not rush it.

---

## Scene 1 — Hook (0:00–0:25) — name the user in the first 30 seconds
**[Screen: Airlock workbench, empty]**

> "Meet the analyst every finance team has: smart, careful — and forbidden from using AI
> agents, because the last one generated code that touched production. What happens when
> an LLM writes code that runs against your customer data? It can delete files, fork-bomb,
> or quietly email the dataset out. Airlock is where that code goes instead: a jail on your
> own Vultr VM — and every task ends with a receipt you can audit. Watch."

## Scene 2 — The real journey (0:25–1:25)
**[Screen: upload `customer_churn_700.csv`, type question]**

> "I'm uploading a customer-churn file our support team would normally email around. I ask
> one question in plain English."

**[Type: "Which contracts and payment methods churn the most? Chart it."]**

> "Airlock's analyst plans the work, writes pandas code, and executes it — inside a sealed
> sandbox on a Vultr VM. Watch the timeline: the sandbox is created with no network,
> CPU and memory caps, a read-only rootfs — my file goes in read-only."

**[Timeline fills; chart appears; answer summarises churn drivers]**

> "There's the chart, there's the answer — built from executed code, not a hallucination.
> And before you see it, a second model looked at the chart and confirmed it actually
> rendered. That verdict is in the receipt too."

## Scene 2b — One breath of architecture (optional, ≤ 10s)
**[Screen: architecture strip on screen]**

> "One Vultr VM, one model endpoint — everything on infrastructure we control."

## Scene 3 — The receipt (1:25–2:05) — the differentiator, do not skip
**[Screen: open containment receipt]**

> "And this is what no sandbox service gives you: a containment receipt. E2B and the
> commercial interpreters isolate — none of them prove what happened. Every model call,
> every line of code executed, every artifact — chained together with SHA-256. If anyone
> tampers with this log, the chain breaks and verification fails on screen. The sandbox
> was created, did its work, and was destroyed. Nothing persists."

## Scene 4 — ATTACK MODE (2:05–3:05) — the containment moment
**[Screen: /attack page]**

> "Talk is cheap. Attack mode isn't. These payloads go through the exact same jailed
> pipeline — nothing is special-cased."

**[Click `rm -rf /` — timeline shows BLOCKED at /, /usr, /etc → sandbox destroyed →
verdict: ABSORBED]**

> "Delete the filesystem? The read-only rootfs and dropped capabilities absorb it."

**[Click exfiltration — BLOCKED: no network]**

> "Steal the data? The sandbox has no network to steal it with."

**[Click fork bomb and memory bomb — killed by pids/memory caps]**

> "Resource bombs? Cgroup caps kill them."

**[Terminal, 10s: `docker ps` during a run → empty after]**

> "And the container is force-removed after every run — there is nothing left to breach."

**[Health chip: service still ok]**

> "The service never even flinched."

## Scene 5 — Why it matters (3:05–3:50)
**[Screen: architecture strip: Browser → Vultr VM (Airlock + gVisor sandbox) → Vultr
Serverless Inference]**

> "Everything runs on a single Vultr VM: the app, the jail, and the LLM calls all go
> through Vultr Serverless Inference. Data in, code jailed, results out, receipt sealed.
> That's the missing trust layer for agent adoption in any industry that touches
> sensitive data. Airlock — the agent is disposable. Your data and infrastructure
> are not."

---
## Shot list / QA
- [ ] 1440p, readable captions, no cursor wandering
- [ ] `rm -rf` absorption lands within first 60s of attack scene
- [ ] URL bar visible (proves it's the live deployment, not localhost)
- [ ] Upload contains "receipt" + "verified chain" moment on screen
- [ ] Total ≤ 4:00; export MP4 (lablab accepts MP4/MOV)
