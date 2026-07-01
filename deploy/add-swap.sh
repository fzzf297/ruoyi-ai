#!/usr/bin/env sh
set -eu

# Add 2GB swap on the target server (run once as root).
# Helps avoid OOM during debug when running multiple services on 1.8GB RAM.

SWAP_FILE="${SWAP_FILE:-/swapfile}"
SWAP_SIZE="${SWAP_SIZE:-2G}"

if swapon --show | grep -q "$SWAP_FILE"; then
    echo "Swap already active: $SWAP_FILE"
    swapon --show
    free -h
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run as root." >&2
    exit 1
fi

echo "Creating ${SWAP_SIZE} swap at ${SWAP_FILE}..."
fallocate -l "$SWAP_SIZE" "$SWAP_FILE" 2>/dev/null || dd if=/dev/zero of="$SWAP_FILE" bs=1M count=2048
chmod 600 "$SWAP_FILE"
mkswap "$SWAP_FILE"
swapon "$SWAP_FILE"

if ! grep -q "$SWAP_FILE" /etc/fstab 2>/dev/null; then
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
fi

echo "Swap enabled:"
swapon --show
free -h
