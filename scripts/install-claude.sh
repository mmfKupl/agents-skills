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

# Register the chat-title reminder as a UserPromptSubmit hook in the user settings,
# keeping every other setting and hook. Running this again changes nothing.
install_hooks() {
  local hook="${claude_home}/hooks/chat-title-reminder.sh"

  mkdir -p "${claude_home}/hooks"
  ln -sfn "${repo_root}/scripts/hooks/chat-title-reminder.sh" "${hook}"
  python3 - "${claude_home}/settings.json" "${hook}" <<'PY'
import json
import sys
from pathlib import Path

path, command = Path(sys.argv[1]), sys.argv[2]
settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
groups = settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
if not any(hook.get("command") == command for group in groups for hook in group.get("hooks", [])):
    groups.append({"hooks": [{"type": "command", "command": command, "timeout": 5}]})
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"Added chat-title hook to {path}")
PY
}

link_skills
install_agents
install_hooks
