---
name: spawn-subagent
description: Launch a fresh subagent with stable delegation defaults. Use when the user explicitly asks to spawn, call, delegate to, or run a subagent and wants quick control over model, reasoning effort, or passed context. Do not use for routine work unless the user explicitly requests delegation or names this skill.
---

# Spawn Subagent

Use this skill only on explicit request.

## Defaults

When the user does not override parameters, call `spawn_agent` with these defaults:

- `model`: the newest generally capable model currently available in the `spawn_agent` tool
- `reasoning_effort`: `xhigh`
- `fork_context`: `false`
- `agent_type`: `default`
- `post_spawn_behavior`: do not wait, do not continue local work, wait for the next user command

Treat "empty context" as "do not fork the current thread history". The subagent still needs a self-contained task message.

## Workflow

1. Confirm the user explicitly wants a subagent. If not, do not use this skill.
2. Extract or infer the delegated task and optional overrides for `model`, `reasoning_effort`, `fork_context`, and `agent_type`.
3. Build a concise self-contained prompt for the subagent, including any required approval gates for code and test changes.
4. Call `spawn_agent` with the resolved parameters.
5. After `spawn_agent`, do not call `wait_agent` by default.
6. After `spawn_agent`, do not continue local work by default.
7. Report briefly that the subagent was launched and then stop, waiting for the next user command.

## Context Handling

Default to `fork_context: false`.

Map common wording like this:

- `empty`, `fresh`, `without context`: set `fork_context: false`
- `current`, `same context`, `inherit context`: set `fork_context: true`
- `minimal`: keep `fork_context: false`, but include only the smallest required facts in the prompt or `items`

Prefer `minimal` over `current` when a few concrete details are enough.

## Agent Type Mapping

Honor an explicitly requested `agent_type` first.

Otherwise map clear task wording like this:

- `find`, `inspect`, `explore`, `analyze`, `trace`, `locate`, `where`, `why`, `how does this work`: use `explorer`
- `implement`, `fix`, `edit`, `change`, `refactor`, `write`, `update tests`, `patch`: use `worker`
- mixed, ambiguous, or strategy-heavy requests: use `default`

Do not overfit on one weak verb. Use `explorer` when the main output is understanding. Use `worker` when the main output is a code or file change.

## Override Rules

Honor explicit user overrides for:

- `model`
- `reasoning_effort`
- `fork_context`
- `agent_type`
- whether to wait for the subagent result
- whether to continue local work in parallel

If the user says "latest model", resolve that against the current `spawn_agent` tool definition instead of hardcoding a stale model name.

If the user says "highest reasoning", use `xhigh`.

If the user does not name `agent_type`, resolve it from the task wording using the mapping above. Fall back to `default` when the intent is mixed or unclear.

If the user explicitly asks to wait, collect the result with `wait_agent`.

If the user explicitly asks to keep working in parallel, continue only the requested local work.

Otherwise prefer an idle handoff: spawn the subagent, acknowledge launch, and wait for the user's next instruction.

## Code Change Gates

When the delegated task may result in code or test edits, include these rules in the subagent prompt:

- Before making any code changes, write in Russian a brief summary of what needs to be changed and wait for explicit user confirmation.
- Do not change tests before the code changes are approved.
- Only after the code changes are approved may the subagent update or add tests.

## Prompt Construction

Write the delegated prompt in imperative form and keep it bounded.

Include:

- the exact task
- the expected output
- relevant file paths, issue IDs, URLs, or artifacts
- whether the subagent should edit files or only investigate
- any approval gates that must be followed before editing code or tests
- ownership boundaries if multiple subagents are involved

Do not assume the subagent can see the prior thread unless `fork_context` is enabled.

Do not leak full thread context by default.

## Examples

- `Use $spawn-subagent to ask a fresh subagent to inspect failing auth tests.`
- `Use $spawn-subagent to delegate this refactor with model gpt-5.4-mini and reasoning high.`
- `Use $spawn-subagent to spawn an explorer with current context and find where rate limiting is implemented.`
