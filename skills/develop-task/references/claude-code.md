# Claude Code runtime adapter

The skills in this repository were written for Codex. When you run inside
Claude Code, apply this mapping before the first delegated job. It changes
only the mechanics: tools, model names, and the delegation backend. Gates,
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

- The `runner` backend (`agent-runner`, `agent-run-manifest`, YAML job
  artifacts) drives the Codex app-server and is not available in Claude Code.
  In Claude Code the backend is always `subagents`. Report it as
  `subagents (Claude Code)` in the first progress update. This is not the
  forbidden silent fallback: the user chose the runtime by invoking the skill
  in Claude Code.
- Do not invoke `agent-runner` or create runner artifacts. For routing
  evaluation and the final usage table, use the usage the Agent tool reports
  for each subagent; where it reports nothing, say so instead of inventing
  numbers.

## Spawning roles

| Codex mechanic | Claude Code equivalent |
| --- | --- |
| `spawn_agent` with a custom role | Agent tool with `subagent_type: "<role name>"` (for example `preflight-review`, `implementation-worker`) |
| `fork_turns: "none"` or bounded history | A fresh Agent call with a compact, self-contained packet. Never use `subagent_type: "fork"` for a gate, specialist, or worker: it inherits the whole conversation and breaks review independence. |
| Explicit model ID | Agent `model` parameter (see the model map below) |
| Explicit reasoning effort | Agent `effort` parameter. This skill explicitly requires it on every delegated job, so always pass it. |
| Follow-up turn to the same live gate or writer | `SendMessage` to that agent's ID. Start a fresh Agent call when the skill asks for a fresh gate or job. |
| Read-only sandbox | Read-only roles are installed with read-only tools only (no Edit or Write). Still state the read-only contract in the packet, because Bash is available to them. |
| Workspace-write sandbox | `implementation-worker` has the full tool set. Keep the single-writer rule: never run two writers at once. |

The custom roles are installed into `~/.claude/agents/` by
`scripts/install-claude.sh` from the shared `agents/*.toml` definitions. If a
role is missing, fail closed exactly as the skill says for an unavailable
role.

## Model map

Map each Codex model name to the Claude model with the same role in the
routing matrix, then use the effort level unchanged (`low`, `medium`,
`high`, `xhigh`, `max`):

| Codex name in the skill | Claude Agent `model` | Claude model |
| --- | --- | --- |
| `gpt-6-luna`, Luna, `gpt-5.6-terra`, Terra | `sonnet` | Claude Sonnet 5.5 |
| `gpt-6.1-sol`, `gpt-6-sol`, Sol, `gpt-5.6-sol` | `opus` | Claude Opus 5.5 |
| `gpt-6-astra`, Astra | `fable` | Claude Fable 5.1 |

`haiku` (Claude Haiku 5.5) has no Codex counterpart in the matrix. Use it
only where the skill allows a cheaper model for a mechanical lookup and the
ceiling forces it, never for a gate.

Model ceilings use the order `haiku` < `sonnet` < `opus` < `fable`. Accept
both Codex names and Claude names in a ceiling (`E Sol` = `E opus`,
`E Luna` = `E sonnet`, `E Astra` = `E fable`). For `M`, the ceiling is the
main session's model at invocation time. Apply the ceiling before every
Agent call, as the skill requires for direct subagents.

When reporting the resolved policy, name the Claude model and, the first
time, the Codex name it maps from (for example `opus high (Sol high)`).

## Task titles

- `list_threads` and `set_thread_title` are Codex app tools. In the Claude
  desktop app, use the session-title tool when it is available
  (`set_session_title`), with the same title format and the same cheap,
  best-effort rules. Otherwise skip titles silently; they are never a gate.

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
  `mcp__hearthbot__update_progress_checklist`. Task titles mean
  `mcp__hearthbot__rename_thread`.
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
