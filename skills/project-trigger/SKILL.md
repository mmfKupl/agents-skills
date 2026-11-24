---
name: project-trigger
description: "Show the triggers a machine has, write a new one from the developer's words, or change one, and save it to the agents-skills repository so that it moves between machines. A trigger says which change in the tracker starts which workflow. Use only when the user writes `$project-trigger` (or `/project-trigger` in Claude Code)."
---

# Project Trigger

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else. It maps `$skill` to `/skill`.

## What this does

A trigger is a file that says "when this happens to a ticket, start that".
[`../project-master/references/triggers.md`](../project-master/references/triggers.md)
holds the format, the commands, and the form in which triggers are shown. Read it
before anything below.

Resolve `agent-projects`:
`${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-projects`, then `PATH`. If it
is missing, stop and tell the developer to run `scripts/install-skills.sh` from the
agents-skills repository.

## Show

`$project-trigger` with nothing after it, or with a question about what exists: run
`agent-projects trigger list` and answer in the form the reference gives for a whole
machine. When the developer names a project, add `--project <project>` and use the
form for a project.

## Write or change

`$project-trigger` followed by what the developer wants, in their words:

1. Run `agent-projects trigger list`. If a trigger there already does what is asked,
   say which and stop. If the request changes one of them, start from its file.
2. Work out the trigger. Ask only what the request leaves open and the answer would
   change: which event, for whose tickets, what starts, and on which model. Propose a
   cheap model for a prompt that only reports, and a strong one for a whole workflow.
3. Write the file into the `triggers` folder of the project files
   (`agent-projects init` prints the folder as `home`), named after the trigger with
   dashes, such as `my-review.yaml`. Keep the name of a trigger you change.
4. Run `agent-projects trigger check <file>` and fix the file until it is accepted.
5. Show the developer the trigger in the form the reference gives, from the check's
   answer, and say in one line that it starts runs with nobody approving them.
6. A trigger is off until a project turns it on. When the developer named a project,
   or this is a project chat, offer
   `agent-projects project triggers <project> --on "<name>"`, and run it on a yes.

## Save to the repository

A trigger in the project files works on this machine only. To move it to other
machines, when the developer asks or says yes to the offer:

1. Find the agents-skills checkout: the folder that
   `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/project-master` links to, two levels up;
   else ask the developer where it is.
2. Copy the file into `skills/project-master/triggers/` there and commit it with a
   message that says what the trigger does. Commit nothing else.
3. Push only when the developer says so.
4. Delete the copy in the project files, so that the repository's version is the one
   in use, and check with `agent-projects trigger list` that the trigger is still
   there, as `ready`. Under Codex the skills are copies, so run
   `scripts/install-skills.sh` first.

## Rules

- Write the trigger's name, prompts, and comments in English.
- A prompt for a run that must not open a pull request or move a status ends with
  `Start nothing.`
- Never put a key, a token, or a person's private data into a trigger.
- Do not turn a trigger on, change a project, or start a run unless the developer
  said so in this chat.
- When the run showed friction, such as a file the check refused although the
  reference allows it, end the answer with a line `Suggestions:`, as
  [`../develop-task/references/suggestions.md`](../develop-task/references/suggestions.md)
  says.
