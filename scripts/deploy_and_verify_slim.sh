#!/usr/bin/env bash
# Slim 栈部署与冒烟（与 deploy_and_verify.sh 相同，但使用 memory overlay）
# 用法: bash scripts/deploy_and_verify_slim.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=/dev/null
source "$(dirname "$0")/docker_host.sh"

export SFP_DATA_ROOT="${SFP_DATA_ROOT:-/workspace/sfp-data}"
bash scripts/sfp_data_init.sh

export COMPOSE_FILE="docker-compose.sentiment.yml:docker-compose.sentiment.slim.yml"
COMPOSE="docker compose"

echo "==> [0/5] compose config（slim + SFP_DATA_ROOT=${SFP_DATA_ROOT})"
$COMPOSE config >/dev/null

echo "==> [1/5] 构建并滚动更新 slim API / jobs"
$COMPOSE up -d --no-deps --build \
  sentiment-backend sentiment-data sentiment-intel sentiment-trade \
  sentiment-jobs

echo "==> [2/5] 等待平台 API 健康（最长 90s），再起前端"
ok=""
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:19099/health >/dev/null 2>&1; then ok=1; echo "backend healthy"; break; fi
  sleep 3
done
[ -n "$ok" ] || { echo "后端未就绪，查看日志: docker logs --tail 50 sentiment-backend"; exit 1; }

$COMPOSE up -d --no-deps --build sentiment-frontend
front_ok=""
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:12580/ >/dev/null 2>&1; then front_ok=1; echo "frontend healthy"; break; fi
  sleep 3
done
[ -n "$front_ok" ] || echo "!! 前端尚未返回 200，继续后续步骤"

echo "==> [3/5] 增量 SQL"
MYSQL_PWD_VAL="${MYSQL_ROOT_PASSWORD:-}"
if [ -z "$MYSQL_PWD_VAL" ] && [ -f .env ]; then
  MYSQL_PWD_VAL="$(grep '^MYSQL_ROOT_PASSWORD=' .env | head -1 | cut -d= -f2- || true)"
fi
if [ -z "$MYSQL_PWD_VAL" ]; then
  MYSQL_PWD_VAL="$(docker exec sentiment-mysql printenv MYSQL_ROOT_PASSWORD 2>/dev/null || true)"
fi
if [ -n "$MYSQL_PWD_VAL" ]; then
  python3 scripts/sql_migrate.py apply --keep-going --password "$MYSQL_PWD_VAL" || true
fi

echo "==> [4/5] 冒烟验证"
ADMIN_PWD_VAL="${ADMIN_PASSWORD:-}"
if [ -z "$ADMIN_PWD_VAL" ] && [ -f .env ]; then
  ADMIN_PWD_VAL="$(grep '^ADMIN_PASSWORD=' .env | head -1 | cut -d= -f2- || true)"
fi
TOKEN=""
if [ -n "$ADMIN_PWD_VAL" ]; then
TOKEN=$(curl -s -X POST http://127.0.0.1:12580/prod-api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"'"$ADMIN_PWD_VAL"'","code":"","uuid":""}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('data') or {}).get('access_token') or (d.get('data') or {}).get('token') or '')" 2>/dev/null || true)
fi
if [ -n "$TOKEN" ]; then
  curl -sf -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:12580/prod-api/market/heat/daily?market=CN" | head -c 120; echo
fi
echo "-- 前端首页: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:12580/)"

echo "==> [5/5] 内存快照（稳态请 Influx healthy 后再跑一次）"
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' 2>/dev/null | head -20 || true
