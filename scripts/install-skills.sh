#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-${HOME}/.codex}"

select_agent_runner_python() {
  local candidate
  local -a candidates

  if [[ -n "${AGENT_RUNNER_PYTHON:-}" ]]; then
    candidates=("${AGENT_RUNNER_PYTHON}")
  else
    candidates=(python3.12 python3.11 python3.10 python3)
  fi

  for candidate in "${candidates[@]}"; do
    if command -v "${candidate}" >/dev/null 2>&1 &&
      "${candidate}" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
      command -v "${candidate}"
      return 0
    fi
  done

  return 1
}

install_agent_runner() {
  local source_dir="${repo_root}/agent-runner"
  local target_venv="${codex_home}/tools/agent-runner"
  local python_bin

  if [[ ! -f "${source_dir}/pyproject.toml" ]]; then
    echo "Agent runner source not found: ${source_dir}" >&2
    return 1
  fi

  if ! python_bin="$(select_agent_runner_python)"; then
    echo "agent-runner requires Python 3.10 or newer" >&2
    echo "Set AGENT_RUNNER_PYTHON to an eligible interpreter" >&2
    return 1
  fi

  "${python_bin}" -m venv "${target_venv}"
  "${target_venv}/bin/python" -m pip install \
    --disable-pip-version-check \
    --force-reinstall \
    "${source_dir}"
  "${target_venv}/bin/agent-runner" --help >/dev/null
  "${target_venv}/bin/agent-run-manifest" --help >/dev/null

  echo "Installed agent-runner to ${target_venv}/bin/agent-runner"
}

remove_obsolete_skills() {
  local skills_dir="${codex_home}/skills"
  local obsolete_skill

  for obsolete_skill in delegation-prompt develop-loop openspec-workflow; do
    if [[ -d "${skills_dir}/${obsolete_skill}" ]]; then
      rm -rf "${skills_dir:?}/${obsolete_skill}"
      echo "Removed obsolete skill ${obsolete_skill} from ${skills_dir}"
    fi
  done
}

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

remove_obsolete_skills
rm -f "${codex_home}/agents/openspec-steward.toml"
install_tree "${repo_root}/skills" "${codex_home}/skills" "skills"
install_tree "${repo_root}/agents" "${codex_home}/agents" "agents"
install_agent_runner
