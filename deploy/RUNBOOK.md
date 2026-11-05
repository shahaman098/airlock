# Airlock VM Deployment Runbook (Vultr → public URL)

## 0. Model IDs verified live (2026-11-05)
`glm-5.3-flash`, `qwen3.8-flash-next`, `mimo-v2.6-flash`, `nemotron-3-nano-omni-30b-a3b-reasoning` — all present in the live catalog (`GET /v1/models`, 35 models). After key arrival run:
```bash
cd backend && .venv/bin/python scripts/live_model_test.py   # proves chat + tools + vision per model
```

## 1. Provision the VM (console.vultr.com)
- **Product:** Cloud Compute — **High Frequency** (or VX1), **2 vCPU / 4 GB**, Ubuntu 24.04 LTS
- **Location:** closest to you (judging is async; latency is irrelevant)
- Firewall/security group: allow 22, 80, 443
- Note the IPv4 address.

## 2. One-command deploy (from the local machine)
```bash
# put your key in backend/.env first (see .env.example), then:
./deploy/deploy.sh root@VM_IP
```
This installs Docker + gVisor, builds the sandbox image, writes the key, starts the
services, verifies health, and prints the public URL. No DNS needed — the bare IP works
(`http://VM_IP/`); add a hostname later for polish.

## 2b. Manual alternative (on the VM as root)
```bash
curl -fsSL https://raw.githubusercontent.com/shahaman098/airlock/main/deploy/install.sh | bash
nano /opt/airlock/airlock.env      # paste VULTR_INFERENCE_API_KEY
systemctl restart airlock
```

## 3. Verify
```bash
curl -s http://VM_IP/health         # docker:true, sandbox_runtime:runsc, inference_configured:true
open http://VM_IP/attack            # run every payload → ABSORBED + verified receipts
docker ps | grep airlock-           # empty between runs (lifecycle discipline)
```

## 4. Submission state checklist
- [ ] `/health` shows `sandbox_runtime: runsc` and `inference_configured: true`
- [ ] Public URL loads from an incognito window
- [ ] One full analysis + one attack run completed through the public URL
- [ ] Receipts page shows verified chains
