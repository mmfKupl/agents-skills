#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${repo_root}/skills"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
target_dir="${codex_home}/skills"

if [[ ! -d "${source_dir}" ]]; then
  echo "Skills source directory not found: ${source_dir}" >&2
  exit 1
fi

mkdir -p "${target_dir}"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude=".DS_Store" --exclude=".system" "${source_dir}/" "${target_dir}/"
else
  cp -R "${source_dir}/." "${target_dir}/"
fi

echo "Installed skills from ${source_dir} to ${target_dir}"
