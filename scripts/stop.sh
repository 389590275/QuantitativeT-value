#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -Eeuo pipefail

# Stop backend and frontend started by scripts/start.sh.
# Usage:
#   cd /data/app
#   bash scripts/stop.sh

APP_ROOT="${APP_ROOT:-/data/app}"
RUN_DIR="${RUN_DIR:-${APP_ROOT}/run}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    log "${name} is not running: pid file not found"
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if ! kill -0 "${pid}" >/dev/null 2>&1; then
    log "${name} is not running: stale pid ${pid}"
    rm -f "${pid_file}"
    return
  fi

  log "Stopping ${name}, pid=${pid}"
  kill -- "-${pid}" >/dev/null 2>&1 || kill "${pid}" >/dev/null 2>&1 || true

  for _ in $(seq 1 15); do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${pid_file}"
      log "${name} stopped"
      return
    fi
    sleep 1
  done

  log "Force stopping ${name}, pid=${pid}"
  kill -9 -- "-${pid}" >/dev/null 2>&1 || kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "${pid_file}"
}

stop_pid_file "frontend" "${RUN_DIR}/frontend.pid"
stop_pid_file "backend" "${RUN_DIR}/backend.pid"

log "Stop completed"
