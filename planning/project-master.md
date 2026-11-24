# Project Master Requirements

## Status

Agreed with the developer in chat on 2026-11-23. All seven steps of the build plan
are written; "Build plan" says what was tried on the VM and what was not. Edit
this file directly; it is the source of truth for what `project-master` must do.

## Goal

The developer runs many agent chats on many tickets at once and loses track of
what is where. `project-master` is one chat per project that:

- takes a ticket and works out what it needs: a review, an investigation, a
  plan, or development;
- watches the tracker and reacts to chosen events without being asked;
- keeps the history of every ticket in files on the machine;
- comes to the developer only for a decision, with choices and a
  recommendation.

## Terms

- **Project**: a set of tickets the developer works on together, for example
  the Linear project "Billing". One `project-master` chat serves one project.
- **Trigger**: a named file that says "when this happens, do that". It replaces
  the earlier word "filter".
- **Check**: a short run on a cheap model that reads one event and picks an
  outcome.
- **Run**: the work a trigger starts: a skill command or a prompt.
- **Current user**: the person whose tracker account the machine uses.
- **Current env**: the machine the agents run on. For UI Bakery it is the VM
  with Remote Control.

## What the developer does

- First call, in the developer's words: "/project-master я хочу вести тут
  задачи связанные по билингу, в линере есть проект с билингом. давай настроим
  всё что нужно для этого". The agent checks what must be set up, asks what to
  watch, proposes triggers, and saves the choices. It confirms the project's name
  with the developer before it creates anything.
- Drops a ticket, with or without a word about it. The agent decides the step,
  asks when unclear, and starts `/review-task`, `/brainstorm-task`,
  `/develop-task`, or `/develop-draft`. In UI Bakery development always runs as
  `/develop-please` together with `/develop-task`.
- Asks about the project: which tasks are where, what waits for the developer.
- Reads reports of runs that triggers started, answers their questions.
- Turns all automatic work off and on again, for example when tokens run low
  or before a vacation.

The mode must also fit projects with no polling at all, or with polling only
for a few named tickets.

## Skills

- `project-master`: the project chat itself.
- `project-scope`: a wrapper for every run that belongs to a project:
  `/project-scope billing /review-task UIB-123`. It tells the agent where and
  how to save the result so that the project sees it, to record that the ticket
  is taken, to write nothing to the tracker, and to message the project chat at
  the end. The watching script puts it in front of every command and prompt by
  itself, so triggers do not repeat it.
- `project-trigger`: saves a new trigger into this repository, or updates one
  there.

## Triggers

A trigger is a YAML file. Ready triggers live with the skill in this
repository (`skills/project-master/triggers/`) and move between machines with
it. Triggers the developer made on a machine live in `agent-projects/triggers/`
there, and any chat may reuse them or start from them.

Rules of the format:

- `on_any` is a list of events. **Any one** entry fires the trigger. Inside one
  entry **every** field must match.
- The fields of `on_any` are checked by the script, with no model and no
  tokens.
- An entry goes to `check` when the trigger has one, unless it names a run
  with `then`.
- `check` runs on a cheap model and answers with exactly one outcome.
- `run` holds one entry per outcome. `command` is a skill call, `prompt` is
  plain instructions. `model` and `effort` are separate fields. `skip` means
  record one line and stop.
- A trigger does not name a project. A project turns triggers on in its own
  file, so one trigger serves any project.

Models work on two levels, with no new routing matrix: the check picks an
outcome, and the outcome names its model and effort. Below that, the skill
that was started routes its own agents with its own matrix. Model names follow
the table in `skills/develop-task/references/claude-code.md` (haiku = Luna,
sonnet = Terra, opus = Sol, fable = Astra), so the same file works under Claude
and Codex.

### `my review`

```yaml
name: my review
on_any:
  - source: linear
    event: status_changed
    to: In Review
    assignee: current_user
    actor: not_current_user
    skip: ticket_taken_in_current_env   # a chat here already works on it
    then: review
  - source: linear
    event: comment_added
    ticket: reviewed_in_current_env     # a review of it is on record here
    skip: agent_comment
  - source: github
    event: pr_review_or_comment
    ticket: reviewed_in_current_env
    skip: agent_comment
check:
  model: haiku
  effort: low
  prompt: |
    Read the comment, the ticket's record in agent-projects, and the last
    review report. Answer with exactly one outcome:
    - own_review: the current user wrote review remarks themself;
    - author_answered: the author replied to review points, or says the fixes
      are pushed;
    - noise: thanks, status chatter, bots, agent reports.
run:
  review:
    command: /review-task {ticket}
    model: opus
    effort: high
  own_review:
    prompt: |
      Add the current user's remarks to the ticket's record, so that the next
      review run takes them into account. Start nothing.
    model: haiku
    effort: low
  author_answered:
    prompt: |
      Report which review points the author closed, which stay open, and the
      command that reviews the change again. Start nothing.
    model: sonnet
    effort: medium
  noise: skip
```

The files are `skills/project-master/triggers/my-review.yaml` and `my-progress.yaml`,
and `skills/project-master/references/triggers.md` is the format that agents read.
The script refuses a file with anything it does not read, so that a misspelled
condition never widens what a trigger starts.

`own_review` only records. The developer chose this on 2026-11-23: their own
comment usually means they have already looked, and a second review costs
several agents on strong models.

### `my progress`

```yaml
name: my progress
on_any:
  - source: linear
    event: status_changed
    to: In Progress
    assignee: current_user
    skip: ticket_taken_in_current_env
  - source: linear
    event: comment_added
    ticket: worked_on_in_current_env    # a record or a PR from an agent here
    skip: agent_comment
  - source: github
    event: pr_review_or_comment
    ticket: worked_on_in_current_env
    skip: agent_comment
check:
  model: haiku
  effort: low
  prompt: |
    Read the event, the ticket's status history in Linear, and the ticket's
    record in agent-projects. Answer with exactly one outcome:
    - new_work_large: the ticket came from a not-started status, has no record
      of earlier work, and is unclear or large;
    - new_work_small: the same, but small and clear;
    - review_feedback: the current user or their agents developed this ticket,
      and a person, the current user included, returned it from In Review or
      In AI Review, requested changes on the PR, listed problems, asked a
      question that blocks approval, or opened a task that came out of the
      review;
    - continuation: earlier work exists and the event adds a requirement or
      answers an open question;
    - noise: thanks, status chatter, bots, agent reports.
run:
  new_work_large:
    command: /brainstorm-task autopilot {ticket}
    model: opus
    effort: high
  new_work_small:
    prompt: Report what to build and the command that starts it. Start nothing.
    model: sonnet
    effort: medium
  review_feedback:
    prompt: |
      Report every point with its link (Linear comment or PR thread), which
      points need code, and the command that continues the developing chat.
      Start nothing.
    model: sonnet
    effort: high
  continuation:
    prompt: Update the ticket's earlier report with what changed.
    model: sonnet
    effort: medium
  noise: skip
```

"Start nothing" stands where a run would open a PR or move statuses. One line
in the trigger replaces it with `/develop-draft` when the developer wants the
draft to start without them.

### Comments from the current user and from their agents

The developer writes review comments themself, and triggers must react to
them. Agents post under the same tracker account: on 2026-11-23 the comments
of UIB-6466 showed `$develop-please:` reports with the developer as the author
and nothing that marks an agent. So the author does not tell a person from an
agent. Two steps separate them:

- `skip: agent_comment` drops what the script can recognize without a model: a
  comment that starts with the name of an agent's skill, such as
  `$develop-please:`, a command for a bot, such as `/e2e-preview`, and anything a
  bot posted. The rule is one for every repository, not a list per repository.
- The check judges the rest: a person's remark against an agent's report.

### In AI Review

No ready trigger. The developer writes one when they want a reaction.

## Project file

```yaml
# agent-projects/project-billing/project.yaml
name: billing
repository: ~/uibakery
tracker: linear
scope:
  linear_project: Billing
triggers: [my review, my progress]
```

`scope` may also be a list of tickets. A project with no `triggers` has no
automatic work.

## Folder on the machine

An initialization script creates the folder on the first call. The agent does
not create it by hand. The script also checks tracker access and that the
watching script runs.

```
agent-projects/
  triggers/                 triggers saved on this machine
  tickets/UIB-1234.md       history of a ticket: who took it, chats, PRs,
                            decisions, reports
  watch.yaml                what the watching script found and what it did
                            with each match
  paused                    present while automatic work is off
  project-billing/
    project.yaml
    reports/                reports of every run of the project
    runs/                   one folder per run a trigger started: its prompt,
                            its answers, and what continues it
```

Ticket history is shared by the whole machine, not by one project or one
skill call. Every workflow skill here (`review-task`, `brainstorm-task`,
`develop-task`, `develop-draft`) and every `project-scope` run records through
a script that a ticket is taken and by which chat, when the folder exists.
`develop-please` stays untouched: in UI Bakery `develop-task` runs with it and
writes the record.

## Watching script

- One script per machine collects fresh changes for every project at once. It
  uses no model. It runs as one service, which the first project chat that
  turns a trigger on installs; later chats find it running.
- It reads the tracker every ten minutes (the developer's choice on
  2026-11-24). Starting what waits and noticing that a run ended need no
  tracker and happen every minute.
- Sources: Linear (status changes with who made them and from which status,
  assignee changes, comments) and GitHub pull requests of watched tickets
  (reviews and comments).
- It matches each change against the `on_any` entries of the triggers that
  projects turned on. It reads the taken records itself, so a ticket that a
  chat already works on costs no agent call.
- A status entry is judged by where the ticket is now, not by a stream of
  changes: the ticket is in the entry's status, the move that put it there
  fits the entry, and so does the assignee. So a ticket that was moved to In
  Review and assigned a minute later still matches, and nothing is missed
  while the script was off. One move counts once; a ticket that leaves the
  status and comes back counts again.
- `develop-please` moves a ticket to In Progress as soon as an agent takes it,
  under the developer's account. The script therefore acts on a status change
  only after a short delay, so that the chat that took the ticket has time to
  write its record.
- A ticket goes to one project per trigger. The project that names the ticket
  by number wins over one that covers a whole tracker project; otherwise the
  first project by name gets it. A second project with the same scope gets a
  warning when a trigger is turned on.
- The working copy of a run that a trigger started is removed once its ticket
  is closed in the tracker (Done, Canceled, Won't do, Duplicate). The developer
  asked for this on 2026-11-24. Until then it stays, because the run may be
  continued with an answer. A copy with changes that are not committed is
  kept.
- At project start the agent shows the tickets that already match and asks
  which to run. The script holds them: the first reading after a trigger is
  turned on, and the first after `resume`, starts nothing.
- `/project-master pause` stops polling and new runs on the whole machine;
  runs already going finish. `/project-master resume` shows what came in
  meanwhile and asks what to run.

## Starting agents

Every check and run starts through `agent-runner`, as in `develop-task`. The
runner already picks Claude or Codex by the model name.

- A check fits the runner as it is, as a new read-only role.
- A run of a whole skill does not fit a runner job: a job has a fixed tool
  list, no skills, no subagents, no tracker connection, and cannot be
  continued. The runner gets a second kind of launch, a full chat: skills and
  connections on, model and effort from the trigger, saved so that it can be
  continued after the developer answers, with status and tokens recorded as
  for a job.

Where a chat shows up:

- A run that a trigger started stays out of the sidebar.
- A task the developer asked for by hand opens a chat in the sidebar.

Under Claude Code on the VM that is a launch without Remote Control and a
launch with it.

## Results, questions, notifications

- A run writes its report into the project's `reports/` folder and the
  ticket's history. A chat the developer started by hand then messages the
  project chat itself. For a run that a trigger started, the watching script
  sends that line when the run ends, through a small chat on the cheapest
  model, because only a chat can message a chat. It also sends a line when
  the run failed or filed no report.
- The project chat sends a notification to the Claude app when a report is
  ready or a decision is needed and the developer is not in the chat.
- A background `/brainstorm-task` runs in `autopilot`, with no questions. When
  a run still stops on a question, the question goes to the project chat, the
  developer answers there, and the run continues with the answer.
- `project-master` re-reads the project folder for messages about status, not
  for every message.

## Tracker rules

- Nothing is written to Linear or to a PR unless the developer says so.
- A review always ends with an offer to post the review to the ticket.
- Our skills never move statuses. In UI Bakery only `develop-please` does.
- The tracker depends on the repository. UI Bakery uses Linear. A repository
  with no tracker keeps its tasks in local files in the project folder.
- Repository notes live in `skills/project-master/references/`, one file per
  repository, read only inside that repository, as
  `skills/develop-task/references/ui-bakery.md` is today. For UI Bakery:
  tracker, status names, development through `/develop-please` with
  `/develop-task`, and the `$develop-please:` comment marker.
- Not now: moving tickets back to In Progress automatically.
- No limit on the number of tasks.

## Any agent

Files and scripts are shared by every agent. What differs per application
(how to open a visible chat, how to notify) goes into a short reference file
per application, as `skills/develop-task/references/claude-code.md` is today.

## Linear access

The watching script needs a personal API key, because a script without a model
cannot use the agent's Linear connection.

- The key is read-only and limited to the UIB team. The developer saved one
  on the VM on 2026-11-24. Linear shows it as the developer's own account with
  the UIB team only; that it is read-only was not checked, because the only
  check from outside is an attempt to write.
- It lives in a file outside any repository,
  `~/.config/agent-projects/linear-api-key`, mode 600, and not in a shell
  startup file.
- The developer types it at initialization, without echo. No agent sees it or
  enters it.
- The script reads the file itself and sends the key only in the request
  header.

On the VM every agent runs as the same user with passwordless sudo, so no way
of storing the key hides it from agents. The read-only, team-limited key is
what limits the damage.

## Checked on 2026-11-23

On the VM, Claude Code 2.1.330 and Codex 0.171.0:

- A script-started run continues with its context after an answer:
  `claude -p --resume`, `claude --bg --resume`, `codex exec resume`.
- A run started with `claude --bg --remote-control <name>` appears in the
  developer's sidebar. A run started with plain `claude --bg` or `claude -p`
  does not.
- A `claude -p` run sent a message to an idle chat on the same machine. The
  chat started a turn and sent a notification, which reached the developer's
  phone.
- A run can send that notification itself only with Remote Control on, and
  not in the first minutes after its start.
- Chats created from the app have their own tools to create a chat and to
  message one. Since 2026-11-23 writes through them fail with an approval
  error. Messages between chats on one machine do not pass through that
  server and are not affected.
- Linear reports for each change who made it, the previous and new status,
  and the previous and new assignee. A comment has an author and a text.
- UIB statuses: Triage, Backlog, Planned, Todo, In Progress, Pending, In
  Review, In AI Review, Done, Won't do, Canceled, Duplicate.
- The VM has the Linear connection for Claude and for Codex, no API key, no
  Linear CLI, and `gh` logged in. Linear has no official CLI that one search
  could find.

## Build plan

Each step is useful by itself and is tried on real tickets before the next
one starts.

1. **Folder and records.** A command `agent-projects` in the `agent-runner`
   package, installed next to `agent-runner`, so every skill and both hosts
   find it the same way. It creates the folder, creates and shows projects,
   records that a ticket is taken or released, keeps the ticket history, files
   reports, and prints the status of a project. Unit tests in
   `agent-runner/tests`.
2. **Manual mode.** The skills `project-master` and `project-scope`, with a
   reference file per host for opening a visible chat and sending a
   notification, and a reference file for UI Bakery. No watching yet:
   `project-master` takes a ticket, decides the step, starts the skill in a
   visible chat, and answers questions about status from the folder and the
   tracker.
3. **Records from the workflow skills.** `review-task`, `brainstorm-task`,
   `develop-task`, and `develop-draft` record a ticket as taken at the start
   and released at the end when the folder exists.
4. **Runner.** A read-only check role, and the second kind of launch, a full
   chat.
5. **Watching, first trigger.** The Linear key, the watching script as a
   service, trigger files, `my review` with its status event, the message to
   the project chat, the notification, `pause` and `resume`.
6. **Comments and `my progress`.** Comment events from Linear and GitHub, the
   check, the outcomes.
7. **`project-trigger`** and the host notes for Codex.

Steps 1 to 3 are the manual part and need no Linear key and no runner change.

Status on 2026-11-23: steps 1 to 3 are written and were tried once on the VM
under Claude Code, on UIB-6602 in a project for "Droys Agent". The project chat
set the project up without questions, chose a review, and started a visible chat
in its own working copy. That chat recorded the ticket, ran the review, filed the
report, and messaged the project chat, which passed the outcome on. Nothing was
written to Linear or the pull request. Two defects found there are fixed: the
project chat recorded a title it did not have, and it sent no notification. Not
tried: brainstorm and development steps, a ticket another chat holds, Codex.

Step 4 is written on 2026-11-24: the role `project-check` and the commands
`agent-run-manifest chat` and `chat-resume`, described in `agent-runner/README.md`.
Both were tried on the VM under Claude Code (haiku) and Codex (Luna). The check
sorted a review comment as `review_feedback` and ignored an instruction planted in
the comment. A chat kept its context across two turns, had the skills, and stayed
in its own working copy.

Step 5 is written on 2026-11-24: the commands `agent-projects watch`, `pause`,
`resume`, `trigger list`, and `project triggers`, described in
`agent-runner/README.md`, and the trigger file `my-review.yaml`. Tried on the VM
under Claude Code, with a project for "Droys Agent" that a project chat set up:

- The chat offered the triggers with a recommendation, turned them on, showed the
  one ticket that already matched, and started it only on a yes.
- The script started the run within a minute, in a working copy of its own. The
  run recorded the ticket, filed its report, and released the ticket.
- Defect found and fixed: the run, on Sonnet, skipped the message to the project
  chat. The script sends that line now. In the second run the line arrived, the
  project chat read the report, answered, and requested a notification.
- `pause` and `resume` through the chat, and the service (`watch install`, then
  `uninstall`), worked.
- Nothing was written to Linear or to a pull request. Everything the trial made
  on the VM was removed, and the service is not installed there.

Not tried: `my review` itself on a real ticket, because no ticket matched it at
the time (the trial used a throwaway trigger on In AI Review with a two-line
prompt); a run that fails; an answer sent to a run with `chat-resume`.

Steps 6 and 7 are written on 2026-11-24. Step 6: comment entries for Linear and for
the ticket's pull request, the check, both ready triggers in full. Step 7: the skill
`project-trigger`, the format reference, plain-words listing of triggers
(`agent-projects trigger list`, with `--project`), and what Codex can and cannot do,
in `skills/project-master/references/hosts.md`. The developer also asked on
2026-11-24 for the triggers of a project and of the whole machine to be shown clearly;
the form is in the format reference.

Tried on the VM on 2026-11-24, from the repository checkout, because the installed
runner was busy with the developer's own job. A record of a review of UIB-6602 was
made by hand, and its three real comments of 2026-11-23, written by the developer
within two minutes, were made to count as new:

- The check on Haiku sorted them as `own_review`. They were held, because it was the
  first reading. One was started: the run on Haiku added the remarks to the ticket's
  history, filed a note, and released the ticket, for under two cents.
- Two defects found and fixed. Three comments were three events with a check and a
  run each; the comments of one reading are one event now. And a run that only
  records would still wake the project chat; a run can be `quiet: true`, and
  `own_review` is.
- Nothing was written to Linear or to a pull request, and the trial's files were
  removed.

Not tried: a review or comment on a real pull request through the script (the query
was run by hand on a real pull request, and the rest is unit-tested with `gh`
replaced); `my progress` on real tickets; an `author_answered` run; `project-trigger`
and the listing of triggers in a real chat; Codex as the host of a project chat.

On 2026-11-24 three independent agents reviewed the watching code: one for bugs, one
for safety, one for code that can be cut. The bug review found one defect that would
have stopped the service and five that needed an unusual situation; the safety review
found four real holes; the reduction review found the code close to lean. All are
fixed in commit `a02fb33` except the two below, and the fixed code read real Linear
and GitHub once on the VM. The service runs there since that day.

On 2026-11-24 the developer asked for four more things, all written the same day:

- A queue: "все задания попадают в очередь а какая-то другая джоба или та же
  самая их берет и запускает смотря сколько сейчас запущено и можно ли запустить
  ещё". The events that wait are the queue, and the loop starts them while fewer
  than the limit run (three; `agent-projects watch limit`). This replaces "no limit
  on the number of tasks" for runs that triggers start.
- A notification when the project chat is closed: the line is kept and a new chat
  takes the project over, then gets the line and notifies.
- A summary once a day per project (`agent-projects watch digest`).
- Cleanup: events that are long over are forgotten with their folders, and working
  copies of chats that recorded a ticket are removed once the ticket is closed.
- A sidebar section per project, on by default and possible to turn off: "по
  умолчанию проджект мастер новый делал так что он двигал себя в сайдбаре в новую
  секцию и все чаты что создавал тоже в этой секции лежали". Each chat files
  itself, because that needs no approval. It works where the application gives the
  tool, which is the Claude desktop app; a chat reached through Remote Control has
  only tags, and a chat started from the shell has nothing.
- Suggestions in every skill: "в скиле develop-task была секция с "что можно
  улучшить". я бы такое добавил во все скилы". Every report ends with what the run
  showed could be better in the skill or the tooling; the rules are in
  `skills/develop-task/references/suggestions.md`. For the project this means: a
  filed report carries the section, the project chat says in one line how many
  suggestions it holds, and the project chat adds a `Suggestions:` line of its own
  only in an answer where friction showed.

Left from the reviews:
- About 22 lines that can be cut, and two commands nobody needs daily
  (`watch uninstall`, `watch run --interval`).
- The chat that only passes one line to the project chat still runs with approvals
  off, because it was not checked whether it can message a chat without that.

## Open points

- Whether a notification always arrives. On 2026-11-23 three of four reached the
  developer's phone, among them the one the project chat sent after a report came
  in, which is the designed path. The one that did not arrive came from the review
  chat of the first trial, although the tool answered "Mobile push requested". The
  cause is unknown.
- Whether the project chat's messages are short enough. After the first trial the
  developer found them long, and the skill now fixes what each of its three
  messages holds. A second short trial showed the shorter messages.
- Under Codex a project chat cannot open a visible chat, be messaged, or notify:
  `codex exec` 0.171 has only tools for its own sub-agents. The Codex app was not
  checked. Runs on Codex models work.
- A check that answers something that is not an outcome fails the event; the
  developer sees it as failed and can send it to the check again.
- One check reads up to 30 comments of a ticket and 30 reviews of a pull request per
  reading. A busier discussion between two readings loses the oldest.
- The length of the delay before the script acts on a status change. It is two
  minutes now, a guess.
- Time from a status change to the start of a run: up to ten minutes until the
  next reading, then up to a minute. After the run, up to a minute to notice the
  end, and the small chat that passes the line on.
- Removing working copies of closed tickets is written and unit-tested, not yet
  tried on the VM. Working copies of chats the developer started by hand are not
  covered: the application removes those with the chat.
- A trigger run works with approvals off, on text that anyone who can edit the
  ticket wrote. That is the same exposure as a review the developer starts by
  hand on the VM, but nobody watches it start.
- The move into the status is looked for in the ticket's last 25 changes. A
  ticket edited more often than that after the move is not matched.
