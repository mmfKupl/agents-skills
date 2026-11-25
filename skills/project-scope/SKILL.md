---
name: project-scope
description: "Run one workflow as part of a project: `$project-scope <project> <command>`. Files the result where the project chat finds it and records the ticket's history. Use only when the user writes `$project-scope` (or `/project-scope` in Claude Code)."
---

# Project Scope

`$project-scope <project> <command>` runs `<command>` as part of the project
`<project>`. The first word after the skill name is the project. Everything after it
is the command, exactly as written:

```
$project-scope billing $review-task UIB-123
```

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else. It maps `$skill` to `/skill`.

## Steps

1. Resolve `agent-projects`:
   `${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-projects`, then `PATH`.
   Run `agent-projects project show <project>`. If the command or the project is
   missing, say so and stop; do not run the command outside the project. If the
   answer has `section: true`, file this chat into the project's sidebar section, as
   [`../project-master/references/hosts.md`](../project-master/references/hosts.md)
   says, once, before the work starts.
2. Run the command as if the developer had written it as this chat's message. A
   `$skill` in it is an explicit invocation of that skill, and all of that skill's
   rules, gates, chat title, and report format apply unchanged. This skill sets no
   title of its own.
3. When the command names a ticket, record it before the work starts:

   ```bash
   agent-projects ticket take <ticket> --workflow <review|brainstorm|develop|draft> \
     --project <project> --title "<this chat's title>"
   ```

   A workflow that records the ticket itself then finds the record already there. For
   a command that is none of these workflows, use `--workflow other` and, for the
   report, a one-word kind of your own, such as `note`.
4. When the command reaches its final report, or stops blocked:
   - file the report, with the same text the developer gets, on standard input:
     `agent-projects report add --project <project> --ticket <ticket> --kind <review|brainstorm|develop|draft>`;
   - release the ticket: `agent-projects ticket release <ticket> --result "<one line: the outcome>"`.
     Write the line in the language of the report: the project chat shows it to the
     developer as it is, as the outcome of the step;
   - tell the project chat in one line, as
     [`../project-master/references/hosts.md`](../project-master/references/hosts.md)
     says: `<ticket>: <kind> report ready, <the outcome in a few words>. <path>`. Run
     `project show` again for the chat's name, which may have changed since step 1.
     The project chat notifies the developer; notify them from this chat only when
     the project chat cannot be reached;
   - end the final answer with the line `Saved to project <project>: <path>`.

A line under the command that begins with `Started by the trigger` or with
`Started from the project chat` comes from the watching script, not from the
developer. Then nobody reads this chat:

- never wait for an answer; put each question into the report with its choices and a
  recommendation;
- do not message the project chat and do not notify the developer: the watching
  script passes the report on when this chat ends. Filing the report and releasing
  the ticket stay;
- in a chat that has no title, record the ticket with the title `<kind>: <ticket>`.

A command with no ticket files nothing; say so in one line. The report is never held
back or shortened because of these steps. If one of them fails, say which in one line
and carry on.

The report ends with `Suggestions`, as
[`../develop-task/references/suggestions.md`](../develop-task/references/suggestions.md)
says. When the command's skill has that section, put friction from this skill's steps
there too; when it has none, add the section.

## Project rules

These apply on top of the command's own rules.

- Write nothing to the tracker or to a pull request unless the developer says so in
  this chat, or the command's own workflow owns that write, as `$develop-please` owns
  the status and the reports of the ticket it develops.
- A review asks, in the `Needs from you` section of its report, whether to post the
  review to the ticket. Post it only on a yes.
