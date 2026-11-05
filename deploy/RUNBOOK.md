# Airlock VM Deployment Runbook (Vultr → public URL)

## 1. Provision the VM (console.vultr.com)
- **Product:** Cloud Compute — **High Frequency** (or VX1), **2 vCPU / 4 GB**, Ubuntu 24.04 LTS
- **Location:** closest to you (judging is async; latency is irrelevant)
- Enable **Auto Backups off** (cost), **Cloud firewall: allow 22, 80, 443**
- Note the IPv4 address.

## 2. Point a hostname at it (production-style URL)
Cheapest credible option: a free subdomain from DuckDNS (duckdns.org) → A record to the VM IP,
then put the hostname in `deploy/Caddyfile` (`yoursub.duckdns.org:80`) and re-run step 4.
Caddy will also serve TLS automatically once the Caddyfile uses the domain with `:443`.

## 3. Install (as root, one command)
```bash
ssh root@VM_IP
git clone <YOUR_REPO_URL> /opt/airlock-src && cd /opt/airlock-src
bash deploy/install.sh
```
The script installs Docker + **gVisor (runsc)**, builds the sandbox image, creates the
`airlock` service user, installs the systemd unit and Caddy, and prints verification steps.

## 4. Configure secrets
```bash
nano /opt/airlock/airlock.env      # paste VULTR_INFERENCE_API_KEY
systemctl restart airlock
```

## 5. Verify
```bash
curl -s localhost:8000/health | jq          # docker:true, sandbox_runtime:runsc
curl -s localhost:8000/                     # workbench UI
docker ps | grep airlock-                   # empty between runs (lifecycle discipline)
# public:
curl -s http://VM_IP/health
# containment proof:
open http://VM_IP/attack → run every payload → each receipt shows ABSORBED + chain verified
```

## 6. Submission state checklist
- [ ] `/health` shows `sandbox_runtime: runsc` and `inference_configured: true`
- [ ] Public URL loads from an incognito window (no VPN dependency)
- [ ] One full analysis run + one attack run completed through the public URL
- [ ] Receipts page shows verified chains
