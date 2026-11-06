---
name: chat-title
description: "Keep the chat title in one format, `<status> <type>: <ticket> <description>`, so every chat reads the same in the sidebar. Use in every chat, ideally always: at its start and whenever its status changes. Workflow skills also call it."
---

# Chat title

The title is a best-effort sidebar indicator, never a gate. Only the main session
renames; a subagent or worker does not. Renaming is allowed in read-only work and
authorizes no other change.

## Format

- With a known ticket: `<status> <type>: <ticket-id> <description>`, for example
  `W develop: UIB-5295 Storybook update`.
- Without one: `<status> <type>: <description>`, for example
  `W chat: Agent skills cleanup`.

The status letter and type come first because the sidebar truncates. Write the
ticket ID as plain text, without brackets. Describe the subject in two words, three
at most, with no filler such as "task" or "implementation", and keep the
description stable for the whole chat. If another chat is on the same ticket and
its title is at hand, reuse its description. Rewrite a title in an older format the
next time you rename it. Never rename other chats.

## Type

`chat` for ordinary work. An active workflow sets its own type: `develop`, `draft`,
`review`, or `brainstorm`. Only the workflow the user started sets the type; an
embedded step does not replace it.

## Status

- `W` Working: progressing independently, including waiting for tests, CI, or agents
  that need no reply from the user. Recoverable errors stay `W`.
- `R` Reply needed: pausing for the user's answer, choice, or approval.
- `B` Blocked: stopped by an obstacle such as missing access. Use `R` when the next
  step is the user's decision.
- `D` Done: the requested work is complete, not just this turn. A workflow says what
  done means for it.

Rename at the start, and when the status or the workflow changes, including right
before a blocking question and before the final result. Skip a rename when the title
would not change.

## Tools

| Runtime | Rename | Read current title |
| --- | --- | --- |
| Codex | `set_thread_title` | `list_threads` |
| Claude project thread | `mcp__hearthbot__rename_thread` | none |
| Claude desktop app | `mcp__ccd_session_mgmt__set_session_title` with `session_id: "self"` | `mcp__ccd_session_mgmt__get_session` with `"self"` |
| Claude Code Remote | `mcp__claude-code-remote__set_session_title` with this session's ID | `mcp__claude-code-remote__get_session` without `session_id`, which also gives the ID |

When several exist, use the first that applies, in this order: project thread,
desktop app, Claude Code Remote. These Claude tools are often deferred: load them
with one `ToolSearch` call (`select:<tool>,<tool>`) before deciding they are missing.
If no tool name appears, run one keyword search for
`set_session_title rename_thread`; any tool that renames the current chat counts.

If the user renamed the chat and declines a new title, keep theirs and stop renaming
in this run. If a tool fails or none exists, carry on and try once more at the next
status change. A failed rename never changes the status of the work. Do not poll,
sleep, or ask the user for help just to set a title.
