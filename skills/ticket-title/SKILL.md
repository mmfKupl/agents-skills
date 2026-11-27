---
name: ticket-title
description: "Give tracker tickets a clear title in one format, `<Type>: <clear title>`. Use whenever you work with a ticket, ideally always: when creating one, when starting implementation on one, and to suggest a better title when only reading one. Workflow skills also call it."
---

# Ticket title

A ticket title reads like a PR title: `<Type>: <clear title>`, for example
`Bug: Table loses selection after reload`.

## When to change it

- **Creating a ticket:** use this format.
- **Starting implementation on a known ticket,** once its requirements are
  established: rename it if the title breaks this format or does not say clearly
  what the work is. If later evidence changes the type, for example a bug turns out
  to be a regression, update it once more.
- **Only reading a ticket or answering about it:** change nothing. You may suggest a
  better title.

An outer workflow's own ticket-title rule wins over this one.

In the UI Bakery repository this skill does nothing: it renames no ticket and
suggests no title. There a ticket is named as the repository's
`.codex/skills/linear-issue-writing/SKILL.md` says, by its outcome and with no type in
front, for example `Preserve table filters after refresh`. The team writes its
tickets that way and asks for no renaming.

## Types

- `Feat`: new capability or behavior.
- `Bug`: behavior is wrong, with no evidence that it worked before.
- `Regression`: behavior that worked before broke after a change.
- `Refactor`: structure changes without behavior changes.
- `Perf`: speed or resource use.
- `Chore`: dependencies, build, CI, or tooling.
- `Docs`: documentation only.
- `Test`: tests or test infrastructure only.

## Writing it

Use plain words a teammate understands without opening the ticket: the observable
symptom for `Bug` and `Regression`, the outcome for the rest. Name the affected
area, keep it to about three to eight words, and use sentence case, with no ticket
ID, trailing period, or filler such as "fix", "issue", "problem with", or "task".
Keep the meaning and scope of the original title and requirements, do not state an
unconfirmed cause, and keep the ticket's language unless repository or outer-workflow
rules require another.

## Limits

Rename only the task's own ticket, never related or similar ones, and change only
its title. Keep a leading status prefix that an outer workflow manages, such as
`[Working]` from `$develop-please`, and rename only the part after it. Leave titles that other automation creates or matches, such as
`[E2E Auto]` issues, unchanged. This authorizes no other tracker change. It is best
effort and never a gate: if the tracker tool is unavailable or the edit fails, carry
on and mention it in the final report.
