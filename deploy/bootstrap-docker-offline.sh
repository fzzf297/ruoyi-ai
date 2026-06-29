#!/usr/bin/env sh
set -eu

# Bootstrap Docker from offline bundle on the target machine (no internet).
# Called automatically by install-on-target.sh when docker is missing.

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    exit 0
fi

if [ ! -f "$DEPLOY_DIR/docker-static.tgz" ]; then
    echo "Error: Docker not installed and deploy/docker-static.tgz not found." >&2
    echo "Run deploy/fetch-docker-static.sh on the build machine first." >&2
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: Docker bootstrap requires root." >&2
    exit 1
fi

echo "Installing Docker from offline bundle..."

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "$DEPLOY_DIR/docker-static.tgz" -C "$TMP_DIR"
install -m 755 "$TMP_DIR/docker/dockerd" /usr/local/bin/dockerd
install -m 755 "$TMP_DIR/docker/docker-proxy" /usr/local/bin/docker-proxy 2>/dev/null || true
for bin in containerd containerd-shim-runc-v2 ctr docker docker-init dockerd-rootless-setuptool.sh dockerd-rootless.sh runc; do
    if [ -f "$TMP_DIR/docker/$bin" ]; then
        install -m 755 "$TMP_DIR/docker/$bin" "/usr/local/bin/$bin"
    fi
done

mkdir -p /usr/local/lib/docker/cli-plugins
if [ -f "$DEPLOY_DIR/docker-compose-linux-x86_64" ]; then
    install -m 755 "$DEPLOY_DIR/docker-compose-linux-x86_64" \
        /usr/local/lib/docker/cli-plugins/docker-compose
fi

if ! id docker >/dev/null 2>&1; then
    groupadd docker 2>/dev/null || true
fi

if [ ! -f /etc/systemd/system/docker.service ]; then
    cat > /etc/systemd/system/docker.service <<'UNIT'
[Unit]
Description=Docker Application Container Engine
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/dockerd
Restart=always
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT
fi

systemctl daemon-reload
systemctl enable docker
systemctl start docker

echo "Docker installed:"
docker --version
docker compose version
