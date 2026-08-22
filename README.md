# Agents Skills

Personal Codex skills and custom agents backup and sync repository.

## Layout

- `skills/` - skill folders that can be copied into `${CODEX_HOME:-$HOME/.codex}/skills`
- `agents/` - custom agent TOML files that can be copied into `${CODEX_HOME:-$HOME/.codex}/agents`
- `agent-runner/` - one-shot supervised Codex job runner and atomic run-manifest companion used by `develop-task`
- `scripts/install-skills.sh` - install skills, custom agents, and the runner into local Codex
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

The installer creates a dedicated runner virtual environment at
`${CODEX_HOME:-$HOME/.codex}/tools/agent-runner`. Set `AGENT_RUNNER_PYTHON` when
the preferred Python 3.10+ interpreter is not discoverable as `python3.12`,
`python3.11`, `python3.10`, or `python3`.

## Back up local skills into this repo

```bash
./scripts/backup-local-skills.sh
git status
git add README.md agents planning scripts skills
git commit -m "chore: update personal skills"
git push
```

`backup-local-skills.sh` copies only immediate local skill directories that contain `SKILL.md`. It skips `.system`.
It also skips Codex-managed or superseded skills that should not be backed up here, currently `linear` and `develop-loop`.
It also copies custom agents from `${CODEX_HOME:-$HOME/.codex}/agents/*.toml`.

`install-skills.sh` removes the superseded local `develop-loop` skill before installing, because `develop-task` fully replaces it.

## Current development workflow bundle

Skills:

- `unslop` - shared writing-quality layer used by every skill in this repository for clear, natural user-facing prose.
- `develop-task` - adaptive single-writer repository implementation workflow with mandatory preflight/postflight gates, supervised runner jobs by default, an explicit direct-subagent fallback, focused validation, logical commits, and draft PR creation.
- `diff-review` - independent fresh diff review for local changes.
- `review-task` - deep audit workflow for already implemented tasks, with specialist review, validation reuse, focused checks, and runtime/preview probes when useful.

Custom agents:

- `implementation-worker` - single-writer product-code and test implementation agent selected after preflight.
- `preflight-review` - read-only pre-implementation gate.
- `postflight-review` - read-only post-implementation gate.
- `repo-practice-review` - repository practice and local pattern review.
- `best-practice-review` - general engineering best-practice review.
- `test-review` - focused test strategy and validation review.
- `code-simplicity-review` - scope, simplicity, reuse, and code-quality review.
- `diagnosis-review` - read-only root-cause analysis after an attempted fix leaves the same failure unresolved.
