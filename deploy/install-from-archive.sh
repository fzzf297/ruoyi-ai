#!/usr/bin/env sh
set -eu

# First-time or upgrade install on an air-gapped target from the offline archive.
# No internet required. Installs Docker from bundle if missing.
#
# Usage (as root):
#   sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz
#   sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz /opt/ruoyi-ai

ARCHIVE="${1:-}"
INSTALL_DIR="${2:-/opt/ruoyi-ai}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "Usage: sh deploy/install-from-archive.sh <ruoyi-ai-offline-bundle.tar.gz> [install_dir]" >&2
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run as root." >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Extracting bundle..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

mkdir -p "$INSTALL_DIR"
cp -a "$TMP_DIR/bundle/." "$INSTALL_DIR/"

echo "Installing to $INSTALL_DIR (offline, no downloads)..."
cd "$INSTALL_DIR"
sh deploy/install-on-target.sh
