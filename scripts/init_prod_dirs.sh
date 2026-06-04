#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -Eeuo pipefail

# 创建生产环境数据、日志、运行目录。
# Usage:
#   SAVE_DIR=/data/save LOG_DIR=/data/app/logs RUN_DIR=/data/app/run bash scripts/init_prod_dirs.sh

APP_ROOT="${APP_ROOT:-/data/app}"
SAVE_DIR="${SAVE_DIR:-/data/save}"
LOG_DIR="${LOG_DIR:-${APP_ROOT}/logs}"
RUN_DIR="${RUN_DIR:-${APP_ROOT}/run}"
ENV_FILE="${ENV_FILE:-${APP_ROOT}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  db_path="$(awk -F= '$1 == "DB_PATH" {print substr($0, index($0, "=") + 1)}' "${ENV_FILE}" | tail -n 1)"
  if [[ -n "${db_path}" ]]; then
    SAVE_DIR="$(dirname "${db_path}")"
  fi
fi

mkdir -p "${SAVE_DIR}" "${LOG_DIR}" "${RUN_DIR}"
chmod 755 "${SAVE_DIR}" "${LOG_DIR}" "${RUN_DIR}" 2>/dev/null || true

printf 'Data dir: %s\n' "${SAVE_DIR}"
printf 'Log dir:  %s\n' "${LOG_DIR}"
printf 'Run dir:  %s\n' "${RUN_DIR}"
