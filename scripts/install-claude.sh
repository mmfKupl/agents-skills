#!/usr/bin/env bash
set -euo pipefail

# Install the skills and custom agents from this repository into Claude Code.
# Skills are symlinked so `git pull` updates them; agents are generated from agents/*.toml.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
claude_home="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
skills_dir="${claude_home}/skills"
agents_dir="${claude_home}/agents"

link_skills() {
  local skill_dir name target

  mkdir -p "${skills_dir}"
  for skill_dir in "${repo_root}"/skills/*/; do
    name="$(basename "${skill_dir}")"
    target="${skills_dir}/${name}"
    [[ -f "${skill_dir}/SKILL.md" ]] || continue

    if [[ -e "${target}" && ! -L "${target}" ]]; then
      echo "Skipping ${name}: ${target} exists and is not a symlink" >&2
      continue
    fi
    ln -sfn "${skill_dir%/}" "${target}"
    echo "Linked skill ${name} -> ${target}"
  done
}

install_agents() {
  python3 "${repo_root}/scripts/codex_agents_to_claude.py" "${repo_root}/agents" "${agents_dir}"
}

link_skills
install_agents
