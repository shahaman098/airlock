#!/usr/bin/env bash
# Airlock VM setup — Ubuntu 24.04 on Vultr (run as root, on the VM).
# Clones the repo to /opt/airlock, installs Docker + gVisor (runsc), builds the
# sandbox image, installs the systemd service + Caddy.
set -euo pipefail

APP_DIR=/opt/airlock

echo "==> base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git python3-venv caddy >/dev/null

echo "==> docker"
apt-get install -y -qq docker.io >/dev/null
systemctl enable --now docker

echo "==> gVisor (runsc) — userspace kernel sandboxing"
if ! command -v runsc >/dev/null; then
  curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release/main main" > /etc/apt/sources.list.d/gvisor.list
  apt-get update -qq && apt-get install -y -qq runsc >/dev/null
fi
runsc --version
if docker run --rm --runtime=runsc hello-world >/dev/null 2>&1; then
  echo "runsc runtime verified"
else
  echo "WARNING: runsc verification failed — service auto-falls back to runc (still isolated)"
fi

echo "==> code at $APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone https://github.com/shahaman098/airlock.git "$APP_DIR"
fi
id -u airlock >/dev/null 2>&1 || useradd -r -m -d /opt/airlock -s /usr/sbin/nologin airlock
usermod -aG docker airlock

cd "$APP_DIR/backend"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "==> sandbox image"
docker build -t airlock-sandbox:latest "$APP_DIR/sandbox-image"

echo "==> environment"
cat > /opt/airlock/airlock.env <<'EOF'
VULTR_INFERENCE_API_KEY=__PASTE_INFERENCE_KEY__
AIRLOCK_HOST=127.0.0.1
AIRLOCK_PORT=8000
EOF
chown -R airlock:airlock "$APP_DIR"
chmod 600 /opt/airlock/airlock.env

echo "==> systemd"
cp "$APP_DIR/deploy/airlock.service" /etc/systemd/system/airlock.service
systemctl daemon-reload
systemctl enable --now airlock

echo "==> caddy"
cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl enable --now caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo "==> done. Verify:"
echo "   curl -s http://localhost:8000/health   (service)"
echo "   curl -s http://\$(curl -s ifconfig.me)/health   (public via Caddy)"
