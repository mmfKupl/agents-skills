# Agents Skills

Personal Codex skills and custom agents backup and sync repository.

## Layout

- `skills/` - skill folders that can be copied into `${CODEX_HOME:-$HOME/.codex}/skills`
- `agents/` - custom agent TOML files that can be copied into `${CODEX_HOME:-$HOME/.codex}/agents`
- `scripts/install-skills.sh` - install skills and custom agents from this repository into local Codex
- `scripts/backup-local-skills.sh` - copy local non-system skills and custom agents back into this repository

System skills from `.system` are intentionally not stored here.

## Install on a machine

```bash
git clone git@github.com:mmfKupl/agents-skills.git
cd agents-skills
./scripts/install-skills.sh
```

Use `CODEX_HOME` to install into a non-default Codex home:

```bash
CODEX_HOME=/path/to/.codex ./scripts/install-skills.sh
```

## Back up local skills into this repo

```bash
./scripts/backup-local-skills.sh
git status
git add README.md scripts skills
git commit -m "chore: update personal skills"
git push
```

`backup-local-skills.sh` copies only immediate local skill directories that contain `SKILL.md`. It skips `.system`.
It also skips Codex-managed or superseded skills that should not be backed up here, currently `linear` and `develop-loop`.
It also copies custom agents from `${CODEX_HOME:-$HOME/.codex}/agents/*.toml`.

`install-skills.sh` removes the superseded local `develop-loop` skill before installing, because `develop-task` fully replaces it.
