# Suggestions

Every skill ends its report with `Suggestions`: what this run showed could be better in
the skill itself, in the repository's instructions, or in its checks. The developer
reads them to improve the tooling, so they are about how the work went, not about its
result.

## What goes in

Only friction this run showed:

- a command or context that was hard to find;
- an instruction that was wrong, stale, missing, or at odds with another one;
- a mistake a check could have caught;
- a correction the user says they have given before.

For each, say what happened, what to change, and where: the skill and its section, the
repository file, or the check. Prefer a lint rule, type, test, or CI check; propose a
written rule only when no tool could catch it. Trace each to a specific moment of this
run and change nothing yourself.

## What stays out

- Remarks about the code, the diff, or the task: they belong to the report's other
  sections.
- Advice that no moment of this run backs.
- A question that is already under `Needs from you`.

## Where it goes

- In a report with headings: the last section, `### Suggestions`. Write `none` when the
  run showed no friction.
- In a report that is a list: its last item, `Suggestions`, or `none`.
- In an answer that is not a report, such as a project chat's answer or a listing: a
  last line `Suggestions:` when the run showed friction, and nothing otherwise.
- A skill that runs as a step of another workflow adds no section of its own. The
  workflow that called it writes the one `Suggestions` section and puts the friction
  from its steps there.
