#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -Eeuo pipefail

# Start backend and frontend from /data/app.
# Usage:
#   cd /data/app
#   bash scripts/start.sh

APP_ROOT="${APP_ROOT:-/data/app}"
PYTHON_BIN="${PYTHON_BIN:-}"
NPM_BIN="${NPM_BIN:-npm}"
RUNTIME_ROOT="${RUNTIME_ROOT:-/data/app-runtime}"
FRONTEND_NODE_MODULES_DIR="${FRONTEND_NODE_MODULES_DIR:-${RUNTIME_ROOT}/frontend-node_modules}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
ENV_FILE="${ENV_FILE:-${APP_ROOT}/.env}"
RUN_DIR="${RUN_DIR:-${APP_ROOT}/run}"
LOG_DIR="${LOG_DIR:-${APP_ROOT}/logs}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

setup_node_path() {
  local dir
  for dir in \
    /data/nodejs/bin \
    /data/node/bin \
    /opt/nodejs/bin \
    /opt/node/bin \
    /usr/bin \
    /usr/local/bin \
    /usr/local/nodejs/bin \
    /usr/local/node/bin \
    /root/.nvm/versions/node/*/bin \
    "${NVM_DIR:-}/versions/node/default/bin" \
    "${NODE_HOME:-}/bin" \
    "${APP_ROOT:-/data/app}/runtime/node/bin" \
    "${RUNTIME_ROOT}/node/bin"; do
    if [[ -d "${dir}" ]]; then
      export PATH="${dir}:${PATH}"
    fi
  done

  if ! command -v node >/dev/null 2>&1 && [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  fi
}

node_major_version() {
  node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || echo 0
}

ensure_node_version() {
  local major
  major="$(node_major_version)"
  if (( major < 18 )); then
    echo "Node.js 18+ is required by Vite. Current node: $(command -v node) ($(node -v 2>/dev/null || echo missing))" >&2
    echo "Run scripts/install_deps.sh to install the bundled Node.js runtime, or set NODE_HOME to Node.js 18+." >&2
    exit 1
  fi
}

setup_python_bin() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    if command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      return
    fi
    echo "Missing command: ${PYTHON_BIN}" >&2
    exit 1
  fi

  local candidate
  for candidate in python3.9 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_BIN="${candidate}"
      return
    fi
  done

  echo "Python not found. Install Python 3.9+ or run with PYTHON_BIN=/path/to/python." >&2
  exit 1
}

link_frontend_node_modules() {
  local link_path="${APP_ROOT}/frontend/node_modules"

  mkdir -p "${FRONTEND_NODE_MODULES_DIR}"

  if [[ -e "${link_path}" && ! -L "${link_path}" ]]; then
    rm -rf "${link_path}"
  fi

  ln -sfn "${FRONTEND_NODE_MODULES_DIR}" "${link_path}"
}

ensure_frontend_node_dependencies() {
  link_frontend_node_modules

  if [[ -x "${APP_ROOT}/frontend/node_modules/.bin/vite" ]]; then
    return
  fi

  log "Frontend dependencies missing, installing to ${FRONTEND_NODE_MODULES_DIR}"
  ELECTRON_SKIP_BINARY_DOWNLOAD=1 "${NPM_BIN}" --prefix "${APP_ROOT}/frontend" install
}

env_value() {
  local key="$1"
  if [[ -f "${ENV_FILE}" ]]; then
    awk -F= -v key="${key}" '$1 == key {print substr($0, index($0, "=") + 1)}' "${ENV_FILE}" | tail -n 1
  fi
}

is_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" >/dev/null 2>&1
}

start_process() {
  local name="$1"
  local pid_file="$2"
  shift 2

  if is_running "${pid_file}"; then
    log "${name} is already running, pid=$(cat "${pid_file}")"
    return
  fi

  rm -f "${pid_file}"
  log "Starting ${name}"
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$@" >"${LOG_DIR}/${name}.log" 2>&1 &
  else
    nohup "$@" >"${LOG_DIR}/${name}.log" 2>&1 &
  fi
  echo $! >"${pid_file}"
  sleep 1

  if ! is_running "${pid_file}"; then
    echo "${name} failed to start, check ${LOG_DIR}/${name}.log" >&2
    exit 1
  fi

  log "${name} started, pid=$(cat "${pid_file}")"
}

if [[ ! -d "${APP_ROOT}" ]]; then
  echo "APP_ROOT does not exist: ${APP_ROOT}" >&2
  exit 1
fi

cd "${APP_ROOT}"
setup_node_path
setup_python_bin
bash "${APP_ROOT}/scripts/init_prod_dirs.sh"

if ! command -v "${NPM_BIN}" >/dev/null 2>&1; then
  echo "Missing command: ${NPM_BIN}" >&2
  echo "Current PATH: ${PATH}" >&2
  echo "If Node.js is installed in a custom path, run with NODE_HOME, for example:" >&2
  echo "  NODE_HOME=/usr/local/node bash scripts/start.sh" >&2
  exit 1
fi
ensure_node_version

ensure_frontend_node_dependencies

API_PORT="${API_PORT:-$(env_value API_PORT)}"
API_PORT="${API_PORT:-10002}"
PUBLIC_API_HOST="${PUBLIC_API_HOST:-}"
if [[ -z "${PUBLIC_API_HOST}" ]]; then
  PUBLIC_API_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
PUBLIC_API_HOST="${PUBLIC_API_HOST:-127.0.0.1}"

cat >"${APP_ROOT}/.env.centos-runtime" <<EOF
API_HOST=${PUBLIC_API_HOST}
API_PORT=${API_PORT}
EOF

start_process "backend" "${RUN_DIR}/backend.pid" \
  env API_HOST="${BACKEND_HOST}" API_PORT="${API_PORT}" \
  "${PYTHON_BIN}" "${APP_ROOT}/backend/main.py"

start_process "frontend" "${RUN_DIR}/frontend.pid" \
  env API_HOST="${PUBLIC_API_HOST}" API_PORT="${API_PORT}" \
  "${NPM_BIN}" --prefix "${APP_ROOT}/frontend" run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" --mode centos-runtime

log "Services started"
echo "Backend:  http://${PUBLIC_API_HOST}:${API_PORT}"
echo "Frontend: http://${PUBLIC_API_HOST}:${FRONTEND_PORT}"
echo "Logs:"
echo "  ${LOG_DIR}/backend.log"
echo "  ${LOG_DIR}/frontend.log"
