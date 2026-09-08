#!/usr/bin/env bash
# Phase A: heat / minute-kline / Influx reads only (no MySQL, no login).
# See docker-compose.sentiment.slim.influx-phase.yml
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=/dev/null
source "$(dirname "$0")/docker_host.sh"

export SFP_DATA_ROOT="${SFP_DATA_ROOT:-/workspace/sfp-data}"
bash scripts/sfp_data_init.sh --influx-only

COMPOSE="docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.slim.influx-phase.yml"

echo "==> Starting influx-phase: redis + influx + sentiment-data (--profile influx-phase)"
$COMPOSE up -d ruoyi-redis sentiment-influxdb --profile influx-phase sentiment-data

echo "==> Wait for Influx (18G / ~2992 shards — 12g mem_limit + 4G loop swap on 15G host)..."
for i in $(seq 1 60); do
  if $COMPOSE exec -T sentiment-influxdb influx ping >/dev/null 2>&1; then
    echo "influx healthy"
    break
  fi
  sleep 10
done

echo "==> Done. Market heat/kline APIs need auth once full stack is up."
echo "    Full stack: bash scripts/deploy_and_verify_slim.sh"
