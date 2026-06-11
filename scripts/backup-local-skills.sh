#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
skills_source_dir="${codex_home}/skills"
skills_target_dir="${repo_root}/skills"
agents_source_dir="${codex_home}/agents"
agents_target_dir="${repo_root}/agents"

copy_dir_contents() {
  local source_dir="$1"
  local target_dir="$2"

  mkdir -p "${target_dir}"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude=".DS_Store" "${source_dir}/" "${target_dir}/"
  else
    cp -R "${source_dir}/." "${target_dir}/"
  fi
}

is_excluded_skill() {
  case "$1" in
    linear | develop-loop)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [[ ! -d "${skills_source_dir}" ]]; then
  echo "Local Codex skills directory not found: ${skills_source_dir}" >&2
  exit 1
fi

mkdir -p "${skills_target_dir}"

shopt -s nullglob
for skill_file in "${skills_source_dir}"/*/SKILL.md; do
  skill_dir="$(dirname "${skill_file}")"
  skill_name="$(basename "${skill_dir}")"

  if [[ "${skill_name}" == .* ]] || is_excluded_skill "${skill_name}"; then
    continue
  fi

  copy_dir_contents "${skill_dir}" "${skills_target_dir}/${skill_name}"
  echo "Backed up skill ${skill_name}"
done

if [[ -d "${agents_source_dir}" ]]; then
  mkdir -p "${agents_target_dir}"
  for agent_file in "${agents_source_dir}"/*.toml; do
    cp "${agent_file}" "${agents_target_dir}/"
    echo "Backed up agent $(basename "${agent_file}")"
  done
else
  echo "Local Codex agents directory not found, skipping: ${agents_source_dir}"
fi

echo "Backed up local Codex config from ${codex_home} to ${repo_root}"
