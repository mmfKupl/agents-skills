# Ticket Record

Every chat on a machine can see which tickets the other chats work on. A workflow
that works on a ticket records it. The record is best effort and never a gate, and
only main writes it, never a subagent or a runner job.

Resolve `agent-projects`:
`${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-projects`, then `PATH`. If
the command is missing, skip this file silently.

- At entry, once the ticket is known:

  ```bash
  agent-projects ticket take <ticket> --workflow <review|brainstorm|develop|draft> \
    --title "<this chat's title>"
  ```

  If it prints `skipped`, the machine has no project folder: do nothing more from
  this file. If `also_taken_by` is not empty, tell the developer in one line which
  chat holds the ticket, for what, and since when, then carry on unless they say to
  stop.
- At the end, with the final report or when the workflow stops blocked:

  ```bash
  agent-projects ticket release <ticket> --result "<one line: the outcome>" [--pr <url>]
  ```

- While the chat waits for the developer's answer, the ticket stays taken.
- Only the workflow the developer started records the ticket. An embedded step, such
  as discovery inside `develop-task`, does not.
- A task with no ticket records nothing.
