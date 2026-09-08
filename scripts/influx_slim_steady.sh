#!/usr/bin/env bash
# OPTIONAL: lower Influx to long-term steady-state caps (3g / 2560MiB).
#
# ⚠️  Do NOT run immediately after cold open. cursor-1 peak ~11.7GiB at 12g mem_limit;
# keep headroom until full-stack retest passes and RSS has been idle for days.
#
# Safe to re-run once the above criteria are met.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=/dev/null
source "$(dirname "$0")/docker_host.sh"

COMPOSE="docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.slim.influx-steady.yml"

echo "==> WARNING: Do not run right after cold open. Influx should stay at 12g until full-stack is stable."
echo "==> Press Ctrl+C within 10s to abort, or wait to continue..."
sleep 10

echo "==> Waiting for sentiment-influxdb healthy (skip if already up)..."
for i in $(seq 1 60); do
  if $COMPOSE exec -T sentiment-influxdb influx ping >/dev/null 2>&1; then
    echo "influx healthy"
    break
  fi
  sleep 10
done

echo "==> Applying steady Influx mem_limit (3g) + GOMEMLIMIT 2560MiB (long-term idle only)"
$COMPOSE up -d --no-deps sentiment-influxdb

echo "==> Done. Verify: docker stats --no-stream sentiment-influxdb"
