#!/usr/bin/env bash
# MySQL + Influx 备份到本地目录（默认仓库 backups/，可用 BACKUP_DIR 覆盖）。
# 不写入 git。不 down 容器、不删命名卷。
# SKIP_CD=1：不切到仓库根（容器内只挂载 scripts/ 时使用）。
set -euo pipefail
if [ "${SKIP_CD:-}" != "1" ]; then
  cd "$(dirname "$0")/.."
fi
OUT="${BACKUP_DIR:-$PWD/backups}"
STAMP="$(date +%F_%H%M%S)"
mkdir -p "$OUT"

MYSQL_PWD_VAL="${MYSQL_ROOT_PASSWORD:-}"
if [ -z "$MYSQL_PWD_VAL" ] && [ -f .env ]; then
  MYSQL_PWD_VAL="$(grep '^MYSQL_ROOT_PASSWORD=' .env | head -1 | cut -d= -f2- || true)"
fi
if [ -z "$MYSQL_PWD_VAL" ]; then
  MYSQL_PWD_VAL="$(docker exec sentiment-mysql printenv MYSQL_ROOT_PASSWORD 2>/dev/null || true)"
fi
if [ -z "$MYSQL_PWD_VAL" ]; then
  echo "缺少 MYSQL_ROOT_PASSWORD" >&2
  exit 1
fi

echo "==> MySQL dump"
docker exec -e MYSQL_PWD="$MYSQL_PWD_VAL" sentiment-mysql \
  mysqldump -uroot --single-transaction --routines "sentiment-ai" \
  > "$OUT/mysql-$STAMP.sql"

echo "==> Influx backup"
docker exec sentiment-influxdb influx backup "/tmp/influx-$STAMP" >/dev/null
docker cp "sentiment-influxdb:/tmp/influx-$STAMP" "$OUT/influx-$STAMP"
docker exec sentiment-influxdb rm -rf "/tmp/influx-$STAMP"

echo "完成: $OUT/mysql-$STAMP.sql  $OUT/influx-$STAMP"
