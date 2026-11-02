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

- The `runner` backend (`agent-run-manifest` and its run manifest) reads
  Codex session files and is not available in Claude Code. In Claude Code the
  backend is always `subagents`. Report it as `subagents (Claude Code)` in the
  first progress update. This is not the forbidden silent fallback: the user
  chose the runtime by invoking the skill in Claude Code.
- Home-vendor jobs are Claude subagents. Other-vendor jobs under the skill's
  Cross-Vendor Review (postflight, diagnosis, the Reduction Pass, and the
  specialists postflight or diagnosis request)
  keep the GPT model the matrix names and run through `agent-runner` without a
  manifest, as `references/agent-runner.md` describes under Other-Vendor Jobs.
  Start each runner call with Bash `run_in_background: true` and wait for its
  completion notification instead of polling. The runner needs network access
  and starts `codex`; if the Bash sandbox blocks it, ask the user before
  rerunning it outside the sandbox.
- For routing evaluation and the final usage table, use the usage the Agent
  tool reports for each subagent and the `usage` block of each runner result;
  where nothing is reported, say so instead of inventing numbers.

## Spawning roles

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

| GPT name in the skill | Claude Agent `model` | Claude model |
| --- | --- | --- |
| `gpt-6-luna`, Luna | `haiku` | Claude Haiku 5.5 |
| `gpt-6.1-terra`, Terra | `sonnet` | Claude Sonnet 5.5 |
| `gpt-6.1-sol`, `gpt-6-sol`, Sol | `opus` | Claude Opus 5.5 |
| `gpt-6-astra`, Astra | `fable` | Claude Fable 5.1 |

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

The skill's title format and status rules are the user's standing request, so
apply them in Claude too. Only the main session renames; a subagent cannot
rename the session it runs in.

| Codex tool | Claude desktop app | Claude Code Remote session (Remote Control, claude.ai/code) | Claude project thread |
| --- | --- | --- | --- |
| `set_thread_title` | `mcp__ccd_session_mgmt__set_session_title` with `session_id: "self"` | `mcp__claude-code-remote__set_session_title` with this session's ID | `mcp__hearthbot__rename_thread` |
| `list_threads` | `mcp__ccd_session_mgmt__get_session` with `"self"` for the current title, `mcp__ccd_session_mgmt__list_sessions` for other sessions | `mcp__claude-code-remote__get_session` without `session_id` for this session's ID and title, `mcp__claude-code-remote__list_sessions` for other sessions | skip the snapshot |

Pick the column by which tools exist in the callable or deferred tool list.
When more than one family exists, use the first that applies: project thread,
then desktop app, then Claude Code Remote. In a Remote session, call
`get_session` without `session_id` once at entry and pass the session ID it
returns to every `set_session_title` call.

These tools are usually deferred: they appear by name in the deferred-tool
list but are not callable yet. Before the entry title, load the chosen family
with one `ToolSearch` call, for example
`select:mcp__ccd_session_mgmt__set_session_title,mcp__ccd_session_mgmt__get_session,mcp__ccd_session_mgmt__list_sessions`
or
`select:mcp__claude-code-remote__set_session_title,mcp__claude-code-remote__get_session,mcp__claude-code-remote__list_sessions`.
A title tool missing from the callable list is not unavailable until that load
fails. If none of these names appear at all, run one keyword `ToolSearch` for
`set_session_title rename_thread` before deciding titles are unavailable; a
tool from another server that renames the current session or thread counts.

- Rename at entry, before the first long step, and again at every status or
  workflow change the skill lists, including right before a blocking question
  and before the final result.
- These calls return within about a second, so the skill's Codex wait budget
  and deferral rules do not apply. Call the tool directly. If a call fails,
  continue the work and retry once at the next status change.
- If the user renamed the session themselves, the app may ask them to approve
  the new title. That is expected, not a failure. If they decline, keep their
  title and stop renaming for this run.
- Skip titles silently only when the keyword search finds no rename tool, as
  in a plain terminal CLI, or when a Remote `get_session` result does not
  give the session ID. Titles are never a gate.

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
  `mcp__hearthbot__update_progress_checklist`. Task titles use
  `mcp__hearthbot__rename_thread` as described under Task titles.
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
