# Claude Code runtime adapter

The skills in this repository were written for Codex. When you run inside
Claude Code, apply this mapping before anything else, including the entry task
title. It changes only the mechanics: tools, model names, task titles, and the
delegation backend. Gates,
requirements fidelity, review independence, bounded loops, ownership, and
lifecycle rules stay exactly as the skill describes them.

## Invocation

- `$skill-name` in the skill text means `/skill-name` in Claude Code. Treat
  `/develop-task`, `/review-task`, `/brainstorm-task`, and `/diff-review`
  (with the same trailing arguments, such as `/develop-task E Sol`) as the
  explicit invocations the skills require.
- Mentions of a skill in quoted text, examples, or analysis-only questions
  still do not select it.

## Repository guidance

- Read `CLAUDE.md` files as well as `AGENTS.md` files. When both exist,
  follow both; `CLAUDE.md` wins on Claude-specific details.

## Delegation backend

- The backend rule is the same as in Codex: `runner` by default, `subagents`
  only when the user explicitly asks for them ("используй сабагентов", "не
  используй runner", "use subagents"). Follow `references/agent-runner.md`,
  including `agent-run-manifest`. It reads this session's transcript through
  `CLAUDE_CODE_SESSION_ID`.
- In `runner` mode, home-vendor jobs use the Claude peer model (`agent.model:
  claude-opus-5-5`) and start `claude -p`; other-vendor jobs keep the GPT model
  and start `codex`. The Agent tool is not used for roles. Role contracts come
  from `${CODEX_HOME:-$HOME/.codex}/agents/<role>.toml`, and the runner lives
  under `${CODEX_HOME:-$HOME/.codex}/tools`, so the machine needs
  `scripts/install-skills.sh` as well as `scripts/install-claude.sh`.
- Start each runner call with Bash `run_in_background: true` and wait for its
  completion notification instead of polling. The runner needs network access
  and starts `claude` and `codex`; if the Bash sandbox blocks it, ask the user
  before rerunning it outside the sandbox.
- Runner jobs have no MCP tools, no web tools, and no network. Put ticket text,
  PR comments, and other external evidence in the job prompt. Checks that need
  MCP go to Main validation.
- In `subagents` mode, home-vendor jobs are Claude subagents and other-vendor
  jobs still go through `agent-runner` without a manifest, as
  `references/agent-runner.md` describes under Other-Vendor Jobs.
- For routing evaluation and the final usage table, runner jobs report usage
  through their result files and the reconciled manifest. Main's own usage, and
  Claude subagents in `subagents` mode, where the Agent tool reports only a
  total, come from their transcripts:
  `python3 <this skill>/scripts/claude_usage.py` (it reads
  `$CLAUDE_CODE_SESSION_ID`; pass `--session <id>` otherwise, `--json` for
  machine-readable output). It prints uncached input, cache write, cached
  input, and output with thinking for each subagent ID and for main. Output is
  `n/a` or a lower bound when a Claude Code version did not record final usage;
  keep it that way in the table and mark the totals partial. Match
  rows to jobs by the agent ID the Agent tool returns. Show cache write as its
  own column.
  Fall back to the Agent tool total, marked partial, only when the script
  cannot find the session.

## Spawning roles

This table applies only to the `subagents` backend.

| Codex mechanic | Claude Code equivalent |
| --- | --- |
| `spawn_agent` with a custom role | Agent tool with `subagent_type: "<role name>"` (for example `preflight-review`, `implementation-worker`) |
| `fork_turns: "none"` or bounded history | A fresh Agent call with a compact, self-contained packet. Never use `subagent_type: "fork"` for a gate, specialist, or worker: it inherits the whole conversation and breaks review independence. |
| Explicit model ID | Agent `model` parameter (see the model map below) |
| Explicit reasoning effort | Agent `effort` parameter. This skill explicitly requires it on every delegated job, so always pass it. |
| Follow-up turn to the same live gate or writer | `SendMessage` to that Claude subagent's ID. Start a fresh Agent call when the skill asks for a fresh gate or job. A GPT runner job is one-shot: follow up with a fresh runner job that carries the prior report, as Cross-Vendor Review says. |
| Read-only sandbox | Read-only roles are installed with read-only tools only (no Edit or Write). Still state the read-only contract in the packet, because Bash is available to them. |
| Workspace-write sandbox | `implementation-worker` has the full tool set. Keep the single-writer rule: never run two writers at once. |

The custom roles are installed into `~/.claude/agents/` by
`scripts/install-claude.sh` from the shared `agents/*.toml` definitions. If a
role is missing, fail closed exactly as the skill says for an unavailable
role.

## Model map

Home-vendor jobs map each GPT model in the matrix to its Claude peer and keep
the effort level unchanged (`low`, `medium`, `high`, `xhigh`, `max`):

| GPT name in the skill | Claude Agent `model` | Runner `agent.model` |
| --- | --- | --- |
| `gpt-6-luna`, Luna | `haiku` | `claude-haiku-5-5` |
| `gpt-6.1-terra`, Terra | `sonnet` | `claude-sonnet-5-5` |
| `gpt-6.1-sol`, `gpt-6-sol`, Sol | `opus` | `claude-opus-5-5` |
| `gpt-6-astra`, Astra | `fable` | `claude-fable-5-1` |

Other-vendor jobs keep the GPT model and run through the runner.

Model ceilings use one ladder for both vendors: `haiku` = Luna < `sonnet` =
Terra < `gpt-6-sol` < `opus` = GPT-6.1 Sol < `fable` = Astra. Accept both
names in a ceiling (`E Sol` = `E opus`, `E Terra` = `E sonnet`, `E Luna` =
`E haiku`, `E Astra` = `E fable`). For `M`, the ceiling is the main session's
model at invocation time. A capped job keeps its vendor: under `E Terra`, a
GPT postflight runs on `gpt-6.1-terra`. Apply the ceiling before every Agent
call and every runner task, as the skill requires for direct subagents.

When reporting the resolved policy, name the Claude model and, the first
time, the GPT name it maps from (for example `opus high (Sol high)`).

## Task titles

The `chat-title` skill lists the Claude rename tools and applies here unchanged.

## Other tools

- `update_plan` means the task-list tool your Claude runtime provides.
- `request_user_input` means asking the user (AskUserQuestion when
  available, otherwise a direct question that ends the turn).
- `apply_patch` means the Edit and Write tools.
- Linear, GitHub, and other services: use the MCP servers or CLIs configured
  in this Claude installation (`gh`, the `linear` MCP server). If one is not
  connected, report the gap rather than switching to a different system.

## Claude project threads

When `mcp__hearthbot__*` tools are available, the skill runs in a Claude
project thread. The user reads only messages posted to the thread, often from
a phone and hours later. Apply these rules on top of the mappings above.

- Questions, checkpoints, and approvals: post them with
  `mcp__hearthbot__post_message` and end the turn. The user's reply arrives as
  the next turn; resume from the same gate. Do not use AskUserQuestion: the
  user does not see it.
- Progress: `update_plan` and the task list mean
  `mcp__hearthbot__update_progress_checklist`.
- Results and handoffs: send them with `mcp__hearthbot__post_message`. Text
  outside a hearthbot call reaches nobody.
- Worktree: work in the current checkout. Do not create, switch, or remove git
  worktrees.
- Branch: the thread may start on an assigned `claude/project-thread-*`
  branch. Ignore it and create the task branch from `origin/dev` (or the
  repository default branch) with the skill's naming. Use the `claude/` prefix
  where a skill defaults to `codex/`, and include the Linear issue ID. Use the
  assigned branch only when the user asks for it.
- Dependencies: a fresh thread checkout usually has no `node_modules`. Before
  the first commit, run the repository's setup (for UI Bakery, `npm ci` at the
  repository root) so the Git hooks run. Never bypass hooks instead.
- Long waits (CI, previews, e2e): do not sleep or poll inside a turn. Start
  the wait as a background command (Bash `run_in_background`, for example
  `gh pr checks <number> --watch`), update the checklist with what is
  pending, and end the turn. The command's exit wakes you to continue the
  same wait loop, and user messages can be handled in between. Timeboxes
  still count wall-clock time.
