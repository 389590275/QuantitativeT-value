#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -Eeuo pipefail

# First-time dependency installation for CentOS 7.9.
# Python 3.9 must already be installed. Node.js will be auto-installed if missing.
# Usage:
#   cd /data/app
#   bash scripts/install_deps.sh

APP_ROOT="${APP_ROOT:-/data/app}"
PYTHON_BIN="${PYTHON_BIN:-}"
NPM_BIN="${NPM_BIN:-npm}"
RUNTIME_ROOT="${RUNTIME_ROOT:-/data/app-runtime}"
FRONTEND_NODE_MODULES_DIR="${FRONTEND_NODE_MODULES_DIR:-${RUNTIME_ROOT}/frontend-node_modules}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NODE_VERSION="${NODE_VERSION:-18.20.4}"
NODE_DIST="node-v${NODE_VERSION}-linux-x64-glibc-217"
NODE_ARCHIVE="${NODE_ARCHIVE:-/tmp/${NODE_DIST}.tar.xz}"
NODE_DOWNLOAD_URL="${NODE_DOWNLOAD_URL:-https://cdn.npmmirror.com/binaries/node-unofficial-builds/v${NODE_VERSION}/${NODE_DIST}.tar.xz}"
NODE_FALLBACK_URL="${NODE_FALLBACK_URL:-https://unofficial-builds.nodejs.org/download/release/v${NODE_VERSION}/${NODE_DIST}.tar.xz}"

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

install_frontend_node_dependencies() {
  link_frontend_node_modules

  log "Installing Node.js dependencies to ${FRONTEND_NODE_MODULES_DIR}"
  ELECTRON_SKIP_BINARY_DOWNLOAD=1 "${NPM_BIN}" --prefix "${APP_ROOT}/frontend" install

  if [[ ! -x "${APP_ROOT}/frontend/node_modules/.bin/vite" ]]; then
    echo "Vite was not installed correctly. Check npm output above." >&2
    exit 1
  fi
}

install_node_if_missing() {
  if command -v node >/dev/null 2>&1 && command -v "${NPM_BIN}" >/dev/null 2>&1 && (( "$(node_major_version)" >= 18 )); then
    return
  fi

  local runtime_dir="${RUNTIME_ROOT}"
  local install_dir="${runtime_dir}/${NODE_DIST}"
  mkdir -p "${runtime_dir}"

  if [[ ! -f "${NODE_ARCHIVE}" ]]; then
    log "Node.js not found, downloading ${NODE_DOWNLOAD_URL}"
    download_file "${NODE_DOWNLOAD_URL}" "${NODE_ARCHIVE}" || {
      log "Primary download failed, trying fallback ${NODE_FALLBACK_URL}"
      rm -f "${NODE_ARCHIVE}"
      download_file "${NODE_FALLBACK_URL}" "${NODE_ARCHIVE}" || {
        echo "Failed to download Node.js. Download this file manually to ${NODE_ARCHIVE}:" >&2
        echo "  ${NODE_DOWNLOAD_URL}" >&2
        echo "  ${NODE_FALLBACK_URL}" >&2
        exit 1
      }
    }
  else
    log "Using local Node.js archive: ${NODE_ARCHIVE}"
  fi

  if ! command -v xz >/dev/null 2>&1 && [[ "${EUID}" -eq 0 ]] && command -v yum >/dev/null 2>&1; then
    log "Installing xz for .tar.xz extraction"
    yum install -y xz
  fi

  rm -rf "${install_dir}"
  log "Installing Node.js to ${install_dir}"
  tar -xJf "${NODE_ARCHIVE}" -C "${runtime_dir}"
  ln -sfn "${install_dir}" "${runtime_dir}/node"
  export PATH="${runtime_dir}/node/bin:${PATH}"
  hash -r
}

download_file() {
  local url="$1"
  local output="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fL "${url}" -o "${output}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${output}" "${url}"
  else
    echo "Missing curl/wget." >&2
    return 1
  fi
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    echo "Current PATH: ${PATH}" >&2
    echo "If Node.js is installed in a custom path, run with NODE_HOME, for example:" >&2
    echo "  NODE_HOME=/usr/local/node bash scripts/install_deps.sh" >&2
    exit 1
  fi
}

if [[ ! -d "${APP_ROOT}" ]]; then
  echo "APP_ROOT does not exist: ${APP_ROOT}" >&2
  exit 1
fi

cd "${APP_ROOT}"
setup_node_path
install_node_if_missing
setup_python_bin

need_cmd "${PYTHON_BIN}"
need_cmd node
need_cmd "${NPM_BIN}"

if [[ ! -f ".env" && -f ".env.example" ]]; then
  log "Creating .env from .env.example"
  cp .env.example .env
fi

bash "${APP_ROOT}/scripts/init_prod_dirs.sh"

log "Installing Python dependencies"
"${PYTHON_BIN}" -m pip install -i "${PIP_INDEX_URL}" --upgrade pip setuptools wheel
"${PYTHON_BIN}" -m pip install -i "${PIP_INDEX_URL}" --only-binary=:all: numpy==1.26.4 pandas==2.0.3 "urllib3<2"
"${PYTHON_BIN}" -m pip install -i "${PIP_INDEX_URL}" --prefer-binary -r backend/requirements.txt

install_frontend_node_dependencies

log "Building frontend assets"
"${NPM_BIN}" --prefix "${APP_ROOT}/frontend" run build

log "Dependency installation completed"
echo "App root: ${APP_ROOT}"
echo "Next: bash scripts/start.sh"
