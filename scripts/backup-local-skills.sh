#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
source_dir="${codex_home}/skills"
target_dir="${repo_root}/skills"

if [[ ! -d "${source_dir}" ]]; then
  echo "Local Codex skills directory not found: ${source_dir}" >&2
  exit 1
fi

mkdir -p "${target_dir}"

shopt -s nullglob
for skill_file in "${source_dir}"/*/SKILL.md; do
  skill_dir="$(dirname "${skill_file}")"
  skill_name="$(basename "${skill_dir}")"

  if [[ "${skill_name}" == .* ]]; then
    continue
  fi

  destination="${target_dir}/${skill_name}"
  mkdir -p "${destination}"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude=".DS_Store" "${skill_dir}/" "${destination}/"
  else
    cp -R "${skill_dir}/." "${destination}/"
  fi

  echo "Backed up ${skill_name}"
done

echo "Backed up local skills from ${source_dir} to ${target_dir}"
