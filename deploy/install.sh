#!/usr/bin/env bash
# Airlock VM setup — Ubuntu 24.04 on Vultr (run as root).
# Installs Docker + gVisor (runsc), builds the sandbox image, installs the service + Caddy.
set -euo pipefail

echo "==> base packages"
apt-get update -qq
apt-get install -y -qq ca-certificates curl git python3-venv caddy >/dev/null

echo "==> docker"
apt-get install -y -qq docker.io >/dev/null
systemctl enable --now docker

echo "==> gVisor (runsc) — userspace kernel sandboxing"
(
  curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release/main main" > /etc/apt/sources.list.d/gvisor.list
  apt-get update -qq && apt-get install -y -qq runsc >/dev/null
  runsc --version
  docker run --rm --runtime=runsc hello-world >/dev/null 2>&1 \
    && echo "runsc runtime verified" \
    || echo "WARNING: runsc verification failed — service will fall back to runc (still isolated)"
)

echo "==> airlock service user + code"
id -u airlock >/dev/null 2>&1 || useradd -r -m -d /opt/airlock -s /usr/sbin/nologin airlock
usermod -aG docker airlock

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR/backend"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "==> sandbox image"
docker build -t airlock-sandbox:latest "$APP_DIR/sandbox-image"

echo "==> environment"
cat > /opt/airlock/airlock.env <<EOF
VULTR_INFERENCE_API_KEY=__PASTE_INFERENCE_KEY__
AIRLOCK_HOST=127.0.0.1
AIRLOCK_PORT=8000
EOF
chmod 600 /opt/airlock/airlock.env && chown airlock:airlock /opt/airlock/airlock.env

echo "==> systemd"
cp "$APP_DIR/deploy/airlock.service" /etc/systemd/system/airlock.service
systemctl daemon-reload
systemctl enable --now airlock

echo "==> caddy"
cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl enable --now caddy
systemctl reload caddy || true

echo "==> done. Verify:"
echo "   curl http://localhost:8000/health   (service)"
echo "   curl http://\$(curl -s ifconfig.me)/ (public URL via Caddy)"
