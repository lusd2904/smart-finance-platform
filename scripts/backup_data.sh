#!/usr/bin/env bash
# MySQL 备份到本地目录（默认仓库 backups/，可用 BACKUP_DIR 覆盖）。
# 不写入 git。不 down 容器、不删命名卷。
# SKIP_CD=1：不切到仓库根（容器内只挂载 scripts/ 时使用）。
# 优先 docker exec sentiment-mysql mysqldump；宿主机 mysqldump 仅作兜底。
# 自动轮转保留最近 7 天 mysql-*.sql。不依赖 Influx。
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
if [ -z "$MYSQL_PWD_VAL" ] && command -v docker >/dev/null 2>&1; then
  MYSQL_PWD_VAL="$(docker exec sentiment-mysql printenv MYSQL_ROOT_PASSWORD 2>/dev/null || true)"
fi
if [ -z "$MYSQL_PWD_VAL" ]; then
  echo "缺少 MYSQL_ROOT_PASSWORD" >&2
  exit 1
fi

MYSQL_HOST_VAL="${MYSQL_HOST:-sentiment-mysql}"

echo "==> MySQL dump"
if command -v docker >/dev/null 2>&1 && docker exec sentiment-mysql true >/dev/null 2>&1; then
  docker exec -e MYSQL_PWD="$MYSQL_PWD_VAL" sentiment-mysql \
    mysqldump -uroot --single-transaction --routines "sentiment-ai" \
    > "$OUT/mysql-$STAMP.sql"
elif command -v mysqldump >/dev/null 2>&1; then
  MYSQL_PWD="$MYSQL_PWD_VAL" mysqldump -h "$MYSQL_HOST_VAL" -uroot --single-transaction --routines "sentiment-ai" \
    > "$OUT/mysql-$STAMP.sql"
else
  echo "未找到 docker（sentiment-mysql）或 mysqldump" >&2
  exit 1
fi

find "$OUT" -name "mysql-*.sql" -mtime +7 -delete 2>/dev/null || true

echo "完成: $OUT/mysql-$STAMP.sql"
