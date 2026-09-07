#!/usr/bin/env bash
# Create SFP bind-mount directories under SFP_DATA_ROOT (default /workspace/sfp-data).
# Safe to run repeatedly. Empty mysql/ is OK — MySQL entrypoint will init on first start.
#
# Usage:
#   source scripts/docker_host.sh
#   bash scripts/sfp_data_init.sh
#   bash scripts/sfp_data_init.sh --influx-only   # skip mysql mkdir until Mac shard upload
set -euo pipefail

ROOT="${SFP_DATA_ROOT:-/workspace/sfp-data}"
INFLUX_ONLY=0
if [ "${1:-}" = "--influx-only" ]; then
  INFLUX_ONLY=1
fi

mkdir -p "$ROOT/redis" "$ROOT/influx/data" "$ROOT/influx/config"
if [ "$INFLUX_ONLY" -eq 0 ]; then
  mkdir -p "$ROOT/mysql"
  echo "==> data dirs under $ROOT (mysql/ may be empty until first container init or shard upload)"
else
  echo "==> influx-phase dirs under $ROOT (mysql/ deferred — see docs/SFP-TWO-HOST-DEPLOY.md)"
fi

# MySQL official image runs as uid 999; empty dir must be writable on first init.
if [ -d "$ROOT/mysql" ]; then
  chmod 1777 "$ROOT/mysql" 2>/dev/null || true
fi

ls -la "$ROOT" 2>/dev/null || true
