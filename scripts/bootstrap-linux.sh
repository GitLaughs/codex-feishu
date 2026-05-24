#!/usr/bin/env bash
set -euo pipefail

repo_url="${CODEX_FEISHU_REPO_URL:-https://github.com/GitLaughs/codex-feishu.git}"
checkout_dir="${CODEX_FEISHU_CHECKOUT_DIR:-/opt/codex-feishu}"
node_major="${CODEX_FEISHU_NODE_MAJOR:-22}"
codex_version="${CODEX_FEISHU_CODEX_VERSION:-0.133.0}"
cc_connect_version="${CODEX_FEISHU_CC_CONNECT_VERSION:-1.3.3-beta.2}"
swap_size="${CODEX_FEISHU_SWAP_SIZE:-2G}"
install_swap=1
install_node=1
install_npm=1
clone_repo=1

usage() {
  cat <<USAGE
codex-feishu beginner Ubuntu bootstrap

Usage:
  sudo bash scripts/bootstrap-linux.sh [options]

Options:
  --repo-url URL          Git repository URL. Default: ${repo_url}
  --checkout-dir PATH     Checkout path. Default: ${checkout_dir}
  --node-major N          Node.js major version. Default: ${node_major}
  --codex-version VER     @openai/codex version. Default: ${codex_version}
  --cc-connect-version V  cc-connect version. Default: ${cc_connect_version}
  --swap-size SIZE        Swapfile size. Default: ${swap_size}
  --no-swap               Do not create /swapfile.
  --no-node               Skip Node.js installation.
  --no-npm                Skip global npm packages.
  --no-clone              Skip repository clone/update.
  --help                  Show this help.

This script prepares the Linux host only. It does not write Feishu app secrets,
OpenAI-compatible API keys, user IDs, group IDs, or generated cc-connect config.
After bootstrap, run:

  cd ${checkout_dir}
  bash ./scripts/install-linux.sh
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) repo_url="${2:-}"; shift 2 ;;
    --checkout-dir) checkout_dir="${2:-}"; shift 2 ;;
    --node-major) node_major="${2:-}"; shift 2 ;;
    --codex-version) codex_version="${2:-}"; shift 2 ;;
    --cc-connect-version) cc_connect_version="${2:-}"; shift 2 ;;
    --swap-size) swap_size="${2:-}"; shift 2 ;;
    --no-swap) install_swap=0; shift ;;
    --no-node) install_node=0; shift ;;
    --no-npm) install_npm=0; shift ;;
    --no-clone) clone_repo=0; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/bootstrap-linux.sh" >&2
  exit 1
fi

log() {
  printf '\n== %s ==\n' "$1"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_apt_packages() {
  log "Install apt packages"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    tar \
    unzip \
    build-essential \
    python3 \
    python3-venv
}

create_swapfile() {
  [[ "$install_swap" == "1" ]] || return 0
  if [[ -f /swapfile ]]; then
    log "Swapfile already exists"
    swapon --show || true
    return 0
  fi

  log "Create /swapfile"
  if ! fallocate -l "$swap_size" /swapfile; then
    dd if=/dev/zero of=/swapfile bs=1M count=2048
  fi
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
}

install_nodejs() {
  [[ "$install_node" == "1" ]] || return 0
  if have_cmd node && node -v | grep -q "^v${node_major}\\."; then
    log "Node.js ${node_major}.x already installed"
    node -v
    return 0
  fi

  log "Install Node.js ${node_major}.x"
  curl -fsSL "https://deb.nodesource.com/setup_${node_major}.x" | bash -
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  node -v
  npm -v
}

install_global_npm_tools() {
  [[ "$install_npm" == "1" ]] || return 0
  log "Install global npm tools"
  npm install -g "@openai/codex@${codex_version}" "cc-connect@${cc_connect_version}"
  npm list -g --depth=0 @openai/codex cc-connect || true
}

checkout_repo() {
  [[ "$clone_repo" == "1" ]] || return 0
  log "Clone or update codex-feishu"
  mkdir -p "$(dirname "$checkout_dir")"
  if [[ -d "$checkout_dir/.git" ]]; then
    git -C "$checkout_dir" pull --ff-only
  elif [[ -e "$checkout_dir" ]]; then
    echo "checkout path exists but is not a git repo: $checkout_dir" >&2
    exit 1
  else
    git clone "$repo_url" "$checkout_dir"
  fi
}

install_apt_packages
create_swapfile
install_nodejs
install_global_npm_tools
checkout_repo

log "Done"
printf 'Repository: %s\n' "$checkout_dir"
printf 'Next: cd %s && bash ./scripts/install-linux.sh\n' "$checkout_dir"
