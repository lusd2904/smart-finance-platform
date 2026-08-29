#!/bin/sh
# 立刻备份一次，然后每 86400 秒再备份，直到进程被停。
# 由 compose 服务 sfp-backup 调用；也可本机: bash scripts/backup_loop.sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
while true; do
  if ! sh "$SCRIPT_DIR/backup_data.sh"; then
    echo "backup failed ($?)" >&2
  fi
  sleep 86400
done
