#!/usr/bin/env bash
# One-command remote deploy from the local machine:
#   ./deploy/deploy.sh root@VM_IP [inference_key]
# If the key is omitted, it is read from backend/.env (VULTR_INFERENCE_API_KEY=...).
set -euo pipefail

HOST="${1:?usage: deploy.sh root@VM_IP [inference_key]}"
KEY="${2:-}"

if [ -z "$KEY" ]; then
  ENV_FILE="$(cd "$(dirname "$0")/../backend" && pwd)/.env"
  if [ -f "$ENV_FILE" ]; then
    KEY=$(grep -E '^VULTR_INFERENCE_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
  fi
fi
if [ -z "$KEY" ]; then
  echo "NOTE: no inference key found — deploying in demo mode (set the key later on the VM)."
fi

echo "==> installing on $HOST (5–10 min: docker, gVisor, image build)"
ssh -o StrictHostKeyChecking=accept-new "$HOST" "bash -s" <<'REMOTE'
set -e
command -v git >/dev/null || apt-get update -qq && apt-get install -y -qq git curl >/dev/null
curl -fsSL https://raw.githubusercontent.com/shahaman098/airlock/main/deploy/install.sh | bash
REMOTE

if [ -n "$KEY" ]; then
  echo "==> configuring inference key"
  ssh "$HOST" "sed -i 's|^VULTR_INFERENCE_API_KEY=.*|VULTR_INFERENCE_API_KEY=$KEY|' /opt/airlock/airlock.env && systemctl restart airlock"
fi

echo "==> verifying"
ssh "$HOST" "sleep 2; curl -s http://localhost:8000/health"
echo
IP="${HOST#*@}"
echo
echo "============================================================"
echo "  Public URL:  http://$IP/"
echo "  Attack mode: http://$IP/attack"
echo "  Health:      http://$IP/health"
echo "============================================================"
