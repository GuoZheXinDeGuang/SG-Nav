#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: tools/watch_gpu.sh [interval_seconds]"
  echo "Example: tools/watch_gpu.sh 1"
  exit 0
fi

INTERVAL="${1:-1}"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found. Check NVIDIA driver installation."
  exit 1
fi

if command -v watch >/dev/null 2>&1; then
  exec watch -n "$INTERVAL" -d nvidia-smi
fi

while true; do
  clear
  date '+%F %T'
  nvidia-smi
  sleep "$INTERVAL"
done
