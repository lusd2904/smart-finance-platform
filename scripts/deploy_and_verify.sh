#!/usr/bin/env bash
# 一键部署最新代码到本机 Docker 并做冒烟验证（幂等，可重复执行）
# 用法: bash scripts/deploy_and_verify.sh
# 说明: 只重建业务容器（API/jobs/前端），不触碰 MySQL/Redis/InfluxDB 数据层。
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.sentiment.yml"

echo "==> [1/5] 构建并滚动更新 API / jobs（先于前端，避免 nginx 打到未就绪上游）"
$COMPOSE up -d --no-deps --build \
  sentiment-backend sentiment-market sentiment-news sentiment-quant sentiment-ai sentiment-trade \
  sentiment-jobs sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm

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
[ -n "$front_ok" ] || echo "!! 前端尚未返回 200，继续后续步骤；日志: docker logs --tail 30 sentiment-frontend"

echo "==> [3/5] 增量 SQL（schema_version 登记制，幂等）"
# 密码来源优先级：环境变量 > 根目录 .env > 运行中容器的环境值
MYSQL_PWD_VAL="${MYSQL_ROOT_PASSWORD:-}"
if [ -z "$MYSQL_PWD_VAL" ] && [ -f .env ]; then
  MYSQL_PWD_VAL="$(grep '^MYSQL_ROOT_PASSWORD=' .env | head -1 | cut -d= -f2- || true)"
fi
if [ -z "$MYSQL_PWD_VAL" ]; then
  MYSQL_PWD_VAL="$(docker exec sentiment-mysql printenv MYSQL_ROOT_PASSWORD 2>/dev/null || true)"
fi
if [ -n "$MYSQL_PWD_VAL" ]; then
  # 迁移器按文件名序扫描 sql/ 全部增量，stderr 透传可见；--keep-going 保持旧的容忍度
  if python3 scripts/sql_migrate.py apply --keep-going --password "$MYSQL_PWD_VAL"; then
    echo "增量 SQL 同步完成"
  else
    echo "!! 增量 SQL 存在失败项（错误见上方输出，不再被吞掉）。修复后重跑本脚本可续传"
  fi
else
  echo "!! 未找到 MYSQL_ROOT_PASSWORD，跳过增量 SQL。可手动执行:"
  echo "   python3 scripts/sql_migrate.py apply（或先设置 MYSQL_ROOT_PASSWORD 环境变量）"
fi

echo "==> [4/5] 冒烟验证新接口"
# admin 密码来源优先级：环境变量 > 根目录 .env；未提供则跳过登录冒烟
ADMIN_PWD_VAL="${ADMIN_PASSWORD:-}"
if [ -z "$ADMIN_PWD_VAL" ] && [ -f .env ]; then
  ADMIN_PWD_VAL="$(grep '^ADMIN_PASSWORD=' .env | head -1 | cut -d= -f2- || true)"
fi
if [ -z "$ADMIN_PWD_VAL" ]; then
  echo "!! 未提供 ADMIN_PASSWORD（环境变量或根目录 .env），跳过登录冒烟验证"
fi
TOKEN=""
if [ -n "$ADMIN_PWD_VAL" ]; then
TOKEN=$(curl -s -X POST http://127.0.0.1:12580/prod-api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"'"$ADMIN_PWD_VAL"'","code":"","uuid":""}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('data') or {}).get('access_token') or (d.get('data') or {}).get('token') or '')" 2>/dev/null || true)
fi
if [ -z "$TOKEN" ]; then
  echo "登录失败（可能改过 admin 密码）。跳过接口验证，前端仍已更新。"
else
  echo "-- /dashboard/summary:"
  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:12580/prod-api/dashboard/summary" | head -c 260; echo
  echo "-- /market/index/quotes（非交易时段 items 应为 []）:"
  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:12580/prod-api/market/index/quotes" | head -c 260; echo
  echo "-- /market/heat/daily?market=CN:"
  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:12580/prod-api/market/heat/daily?market=CN" | head -c 200; echo
fi
echo "-- 前端首页 HTTP 状态: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:12580/)"

echo "==> [5/5] 完成。浏览器打开 http://127.0.0.1:12580 → 行情中心 / 舆情AI分析大盘 查看效果"
echo "    强刷浏览器缓存: Cmd+Shift+R"
