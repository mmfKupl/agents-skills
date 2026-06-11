#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-${HOME}/.codex}"

install_tree() {
  local source_dir="$1"
  local target_dir="$2"
  local label="$3"

  if [[ ! -d "${source_dir}" ]]; then
    echo "${label} source directory not found, skipping: ${source_dir}"
    return
  fi

  mkdir -p "${target_dir}"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude=".DS_Store" --exclude=".system" "${source_dir}/" "${target_dir}/"
  else
    cp -R "${source_dir}/." "${target_dir}/"
  fi

  echo "Installed ${label} from ${source_dir} to ${target_dir}"
}

install_tree "${repo_root}/skills" "${codex_home}/skills" "skills"
install_tree "${repo_root}/agents" "${codex_home}/agents" "agents"
