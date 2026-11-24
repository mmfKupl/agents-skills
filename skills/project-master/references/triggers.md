# Triggers

A trigger is a YAML file that says "when this happens to a ticket, start that". A
script on the machine reads the tracker with no model and starts a chat for each
match. This file holds the format and how to show triggers to the developer.

## Where triggers live

- Ready triggers come with the skills: the `triggers` folder next to this skill's
  `SKILL.md`.
- Triggers made on a machine live in the `triggers` folder of the project files
  (`agent-projects init` prints the folder as `home`). One of these wins over a ready
  trigger with the same name.
- A trigger names no project. A project turns triggers on:
  `agent-projects project triggers <project> --on "<name>"`, and `--off`.

## Commands

- `agent-projects trigger list`: every trigger on this machine, in plain words, with
  the projects that have it on.
- `agent-projects trigger list --project <project>`: the same, split into `on` and
  `off` for that project.
- `agent-projects trigger check <file>`: whether the script accepts a file, and how it
  reads it.

## Format

```yaml
name: my review
about: "a ticket was moved to In Review for you by someone else: starts a review"
heading: In review now
on_any:
  - source: linear
    event: status_changed
    to: In Review
    assignee: current_user
    actor: not_current_user
    skip: ticket_taken_in_current_env
    then: review
  - source: linear
    event: comment_added
    ticket: reviewed_in_current_env
    skip: agent_comment
check:
  model: haiku
  effort: low
  prompt: |
    Read the comment and the last review report. Answer with exactly one outcome:
    - author_answered: the author replied to review points;
    - noise: thanks, status chatter, bots, agent reports.
run:
  review:
    command: /review-task {ticket}
    model: opus
    effort: high
  author_answered:
    prompt: Report which review points the author closed. Start nothing.
    label: the author's answer
    model: sonnet
    effort: medium
  noise: skip
```

Three fields hold the trigger's own words for the developer. The project chat shows
them as they are, so write them in the developer's language:

- `about`: the trigger in one line, for the list of triggers in the state of a
  project. Without it the script describes the trigger from its conditions, in
  English.
- `heading`: the heading over the tickets that are under the trigger now, such as
  "In review now". Without it the heading names the trigger.
- `label`, in a run: how the step is called in a line about a ticket, such as
  "review is going". It stands before words like "is going" and "report is ready".
  A run with a `command` needs none when `messages.yaml` next to the project-master
  skill has words for its skill.

- `on_any` lists events. **Any one** entry fires the trigger. Inside one entry
  **every** field must match. The script checks these fields itself, with no model.
- An entry is one of three kinds:
  - `source: linear`, `event: status_changed`: needs `to`, a status name. Optional:
    `from`; `assignee` and `actor`, each `current_user` or `not_current_user`;
    `skip: ticket_taken_in_current_env`, which leaves out a ticket that a chat on this
    machine already works on.
  - `source: linear`, `event: comment_added`: a comment in Linear.
  - `source: github`, `event: pr_review_or_comment`: a review or a comment on the
    ticket's pull request.

  The two comment kinds need `ticket`: `reviewed_in_current_env` (a review of the
  ticket is on record on this machine) or `worked_on_in_current_env` (a chat here
  planned or developed it). Optional: `skip: agent_comment`, which leaves out what no
  person wrote for a reviewer: a comment that starts with the name of an agent's
  skill, such as `$develop-please:`, a command for a bot, such as `/e2e-preview`, and
  anything a bot posted.
- `then` names the entry of `run` that the event starts. An entry with no `then`
  goes to `check`. A comment entry with `then` ignores comments written from the
  current user's own account: with no check, nothing tells the developer from an
  agent that posts under the same account, and a run that comments would start
  itself again.
- `check` is a short job on a cheap model. It gets the event, the ticket, its status
  history, the ticket's record on this machine, and the last report, and answers with
  exactly one outcome. The outcomes are the entries of `run` that no `then` names;
  the prompt says what each means.
- `run` holds one entry per outcome. `command` is a skill call and `prompt` is plain
  instructions; `{ticket}` becomes the ticket's id. `model` and `effort` are separate
  fields. `skip` means: record one line and start nothing.
- `quiet: true` in a run means that the project chat is not told when the run ends,
  for a run that only records something. A run that fails is always passed on.
- Model names: `haiku`, `sonnet`, `opus`, `fable`, or their Codex names `luna`,
  `terra`, `sol`, `astra`. The name decides which application runs the chat. Effort is
  `low`, `medium`, `high`, or `xhigh`.
- Write `Start nothing.` in a prompt whose run must not open a pull request or move a
  status. A run works with approvals off, because nobody is there to approve.
- The script refuses a whole file that has anything it does not read, so that a
  misspelled condition never widens what a trigger starts.

How the script judges an event:

- A status entry is judged by where the ticket is now: it is in the entry's status,
  and the move that put it there fits the entry. One move counts once; a ticket that
  leaves the status and comes back counts again.
- A comment counts from the moment its trigger was turned on, and only for an open
  ticket. The comments that came in since the last reading of a ticket are one event,
  so a discussion starts one check and one run, not one per message.
- The first reading after a trigger is turned on, the first after a pause, and the
  first after the conditions of a trigger that is on were edited, start nothing: what
  matched is held for the developer.
- On a pull request, only people of the repository count (owner, member,
  collaborator), not any GitHub account.
- A file that is refused does not fall back to an older file of the same name.

## Showing triggers to the developer

When the developer asks which triggers there are or which are on, run
`agent-projects trigger list --project <project>`, or without `--project` outside a
project chat, and answer in this form, in the developer's language. Turn the `when`
lines and what they start into plain sentences. Do not print the YAML, the field
names, or the keys of outcomes: say "the author answered", not `author_answered`.
`starts_directly` is what an event starts with no check; `check.outcomes` is what the
check may pick, and nothing else.

```markdown
**On in <project>**

**<name>**
- When: <each `when` line as one sentence, one per line>
- Starts: <what starts directly, with model and effort; then, for events that go through the check, each outcome in words and what it starts>

**On this machine, off in <project>**

**<name>**: <one sentence: when it fires and what it starts>. <ready | made on this machine>; on in: <projects, or nowhere>.
```

A trigger that is off gets its one sentence and no more; the developer asks when
they want the rest. Write `none` under a heading that has nothing. Without a project, use one heading,
**Triggers on this machine**, with the long form for each trigger and a last line
`On in: <projects, or nowhere>`. Add the `problems` of the answer in one line each,
and a trigger that is on but has no file. Leave out file paths unless the developer
asks where a trigger is.
