#!/usr/bin/env bash
# After sentiment-influxdb is healthy, switch Influx to steady-state memory caps (3g / 2560MiB).
# Run once per host after cold open; safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=/dev/null
source "$(dirname "$0")/docker_host.sh"

COMPOSE="docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.slim.influx-steady.yml"

echo "==> Waiting for sentiment-influxdb healthy (skip if already up)..."
for i in $(seq 1 60); do
  if $COMPOSE exec -T sentiment-influxdb influx ping >/dev/null 2>&1; then
    echo "influx healthy"
    break
  fi
  sleep 10
done

echo "==> Applying steady Influx mem_limit (3g) + GOMEMLIMIT 2560MiB (after cold-open 14g phase)"
$COMPOSE up -d --no-deps sentiment-influxdb

echo "==> Done. Verify: docker stats --no-stream sentiment-influxdb"
