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

`scope` may also be a list of tickets, or `assignee: current_user` for every
ticket assigned to the developer, wherever it lies in the tracker. The developer
asked for the last one on 2026-11-24: "хочу тут вести все мои ревью из линера
которые приходят". Their tickets in In Review had no Linear project, so neither
of the first two could cover them. `project create` refuses a `scope` the script
does not read. A project with no `triggers` has no automatic work.

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
  by number wins over one that covers a whole tracker project, and that one
  wins over a project that covers the tickets assigned to the developer; among
  equals the first project by name gets it. A second project with the same
  scope gets a warning when a trigger is turned on.
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

- A run stays out of the sidebar, whether a trigger started it or the developer
  asked for it in the project chat, until the developer asks to open its chat.
  Until 2026-11-24 a task asked for by hand opened a chat in the sidebar; see
  "A step asked for by hand stays out of the sidebar" under the build plan.
- A chat in the sidebar from the start is only for a developer who asks for one,
  and for a machine where watching cannot run.
- A run shows in the project chat while it goes, as a background command under
  Background tasks. See "Work that is going shows in the project chat" under the
  build plan.

Under Claude Code on the VM a run is a launch without Remote Control, and a chat
in the sidebar is a launch with it.

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
- No skill moves a status by itself. In UI Bakery `develop-please` does it during
  development, and the project chat does it when the developer asks there. Until
  2026-11-25 the project chat was told never to: asked to return UIB-6544 to its
  author, it changed the assignee and refused the status. The developer: "я
  попросил перевести тикет мастера а он отказался, я не помню чтобы мы это ему
  запрещали". Returning a ticket to its author in UI Bakery now means the
  assignee and `In Progress` together.
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

- Work that is going shows in the project chat. The developer asked on
  2026-11-24, after a project chat had started two reviews and showed nothing
  while they ran: "можно ли сделать чтобы была какая-то внутри чата карточка с
  анимацией", "или чтобы было видно background tasks", "это нужно не только для
  ревью а для вообще всех запусков работы", and "мы вот сейчас запускаем агента
  через скрипт и потом тот агент пинает основного агента. и это ок. просто визуала
  не хватает". So the delivery of results stays as it was, and the project chat
  keeps one background command per piece of work: `agent-projects ticket wait`
  for a step in a chat of its own, `agent-projects watch wait` for a run from a
  trigger. The command lasts while the work goes and five minutes more; the chat
  stops it when the line about the work arrives. For a run that starts by itself
  the script now sends the project chat a line at the start, so that the chat can
  show it: one more turn of the project chat per such run. Checked the same day
  on the VM: the desktop app lists a background command of a Remote Control chat
  under Background tasks with a timer and a stop button, the chat is woken when
  the command ends by itself, and it is not woken when it stops the command.
- Lines reach a project chat that got a new title. On 2026-11-24 the lines about
  two finished reviews were lost: the project chat had recorded the name
  `bridge-cse-…-db`, the application then titled it "Ревью из Liner в
  project-master", and the small chat that sends a line found no chat under the
  old name. The developer passed on the project chat's suggestion: "стоит брать
  текущее имя чата по id и сохранять строку, если отправка не удалась". The
  script now takes the chat's current name from `claude agents --json` by its id
  before each message, reads the small chat's answer (`sent` or `not sent`), and
  keeps a line that was not sent, to try again an hour later.
- A report the developer can open: "еще есть проблема с отчетами. я вот не могу
  их нормально открыть посмотерть". The application opens only files inside a
  chat's working directory, and reports lie in the project folder outside it.
  `agent-projects report copy <path>` copies a report into `.agent-reports` of
  the working directory and has git ignore that folder through the local exclude
  file; the project chat links the copy. `SendUserFile` delivers a file card
  from a Remote Control chat, but the developer's screenshot of that test showed
  the file pane failing on the path, so the card is not used.
- The chat that did the work can be opened. The developer on 2026-11-24: "эти
  файлы я не могу выделять и добавлять коментраии к каким-то частям. и не могу
  перейти в чат которйы делал ревью". A run from a trigger is a hidden session,
  so its report reached the developer only as a file. `agent-projects watch open
  <id> --title "<title>"` continues that session as a chat in the sidebar: the
  report is its last message, where the developer can select a part and answer
  with a quote, and the agent that answers has the whole review in its context.
  Asked whether the script should open such a chat after every review, the
  developer chose "Только по просьбе": the project chat opens one only when
  asked. Checked on the VM the same day with the UIB-6626 review and two
  stand-in runs: the developer saw the earlier conversation in the opened chat;
  a working copy that was gone could be put back with git; opening a chat that
  runs starts a copy, so the command looks first; a stopped chat wakes with its
  saved title when no options are passed. Not built, because nothing asked for
  them: comments on a published page (an artifact), and comments on the lines of
  a report through the application's view of changes.
- A short word when tickets come and go. The developer on 2026-11-24: "хочется
  чтобы после того как я тикет закинул в done или мне пришел новый тикет по
  тригеру то в основной чат писалось ОЧЕНЬ краткое сообщение с сылкой на тикет +
  названием и статусом и кратко по всем тикетам что подподают сейчас под условия
  тригера", with this example: "тикет 123 закрыт успешно / тикеты в ревью: / 321
  бла бла - ревью готово ждет тут / 231 бла бла - ревью в процессе". Until then a
  closed ticket only had its working copies removed, and the project chat heard
  nothing. At each reading the script now keeps the list of tickets that are
  under each trigger of a project. When a ticket comes under a trigger or leaves
  it (closed, another status, another assignee), the project chat gets one
  message, `Tickets changed in <project>`: what changed, then every ticket under
  a trigger now with where it stands here. It replaces the line about the start
  of the run for a ticket that has just come. A closed ticket that has a record
  on the machine gets a line in its history.
- The board is printed by the script. The developer on 2026-11-24, about the
  first answer of a project chat that listed every ticket assigned to them by
  status and described the triggers in a paragraph each: "очень путает с бивает.
  я не понмаю причем тут тикеты котоыре под тригер не подпадают", "какие тригеры
  включены нунжно писать как-то понятнее и компактнее", "нужны шаблоны или скрипт
  для агента чтобы он эту инфу выводил не придумывая каждый раз".
  `agent-projects board <project>` prints what the project covers, each trigger
  in one line with ON or off, the tickets under the triggers that are on with
  where each stands, and what else is not over. The project chat shows it as
  printed, in its first answer and for a question about status, and lists no
  other tickets.
- A step asked for by hand stays out of the sidebar. The developer on
  2026-11-24, after sending the project chat a ticket and seeing the review as a
  row next to the project chat: "мне не нравится что оно вот так в сайдбаре
  видно. я думал оно будет как нестед чат или не будет видно в целом". No
  way was found for a chat on the VM to nest one chat under another: the
  desktop documentation (code.claude.com/docs/en/desktop, read the same day
  except for its last part) lists a started session under the current one only
  for sessions that the desktop app starts itself, and a Remote Control chat
  has no tool for sidebar sections. So such a step now runs the way a trigger's run does.
  `agent-projects watch add <project> <ticket>` reads the skill call and the
  developer's words on standard input and queues an event; the watching script
  starts it out of the sidebar within a minute, shares the limit of three runs,
  and sends the line when it ends. The project chat shows it with
  `agent-projects watch wait`, and `agent-projects watch open` opens its chat
  when the developer asks. The command refuses when watching does not run and
  when the ticket has an event going already.
- The model of a step asked for by hand. The developer asked the same day: "и
  как мастер выбирает на какой модели ревью запускать?". Until then the project
  chat did not choose: a chat it started in the sidebar ran on the default
  model of Claude Code on the machine (the review of UIB-6674 ran on
  `claude-opus-5-5`; `~/.claude/settings.json` on the VM names no model), while
  a trigger's run took the model and effort from the trigger file. Now
  `watch add` gives a step what a trigger on the machine gives the same skill,
  a trigger of the project first: `opus` and `high` for `review-task` under `my
  review`. With no such trigger it is `opus` and `high`. `--model` and
  `--effort` are for a developer who names another, and the project chat says
  the model in its line about the start.
- The typical messages are written by the script, not by the project chat. The
  developer on 2026-11-24: "давай еще подумаем как сделать так чтобы мастер агент
  на типичные вещи отвечал шаблонно и сам не придумывал текст. например вот
  ответы после тригерров и тд. мб это нужно рядом с тригером писать шаблоны
  ответа", and then, offered a choice of where the templates live and in which
  language: "сделай как думаешь будет лучше. я тебе доверяю". The record of the
  project chat of that day showed twelve typical answers, of which the script
  wrote one (the state of the project), and the chat retold a report in its own
  words each time: where the report said "Публиковать этот обзор в тикет
  UIB-6674? Рекомендую: да.", the chat wrote "Опубликовать обзор в тикет: да или
  нет? Рекомендую да.". Now:
  - Three commands print text that the chat shows as it is: `agent-projects
    board <project>` (the state of the project), `agent-projects board <project>
    <ticket>` (one ticket in full), and `agent-projects news <project>` (what
    happened since the chat last asked). A command that changes something answers
    with a line under `say`.
  - One ticket reads the same in every message: its number as a link, its title,
    and where it stands, from a closed list of states.
  - The text about a report takes the report's `Verdict` and `Needs from you`
    sections as they are written, links a copy of the report that the application
    can open, and counts the suggestions. Reports are written in the developer's
    language already, and their headings are the same in every workflow.
  - News is kept per project in `news.yaml` and read by the chat, so the text does
    not pass through the small chat that wakes the project chat. A line that
    arrives only says that there is news. A report becomes news the moment it is
    filed, whoever filed it.
  - What the chat needs for its own steps (which background command to start or
    stop, which notification to send, which command opens a chat) follows the
    line `=== for the chat, not for the developer ===` and is not shown.
  - The words are in one file, `skills/project-master/messages.yaml`, in Russian,
    over English ones in `agent-runner/project_messages.py`; a file of the same
    name in the projects folder of a machine wins. A trigger file holds only the
    trigger's own words: `about` and a `label` for a run with a prompt (a
    `heading` over the trigger's tickets was dropped on 2026-11-25, see below). Whole templates per trigger were not built: the sentences are the
    same for every trigger, and half of the messages have no trigger.
  - Left to the chat's own words: a question to the developer, an answer that
    these texts do not cover, and a problem with a command.
- A ticket sent by hand with no step named goes through a trigger's check. The
  developer on 2026-11-24, about a project chat that had `my progress` on: "я
  сказал \"давай делать два тикета\" и я ожидал что будет так, что как для
  тригера my progress будет анализ что делать с тикетом от хайку и потом запуск
  что хайку сказал, но в итоге они пошли на разработку". The chat had taken
  "давай делать 6667 и 6666" as development and queued `develop-please` for
  both, on opus: by the skill it chose the step itself, and a check ran only for
  what the tracker reported. Now only words that name a step count as naming it.
  For any other ticket that wants work the chat runs `agent-projects watch add
  <project> <ticket> --trigger "<trigger>"`: the script reads the ticket from
  Linear, writes the same packet as for a status change, and the trigger's check
  (haiku for `my progress`) sorts it; what the outcome names starts, with the
  developer's words under the command. What the check picked comes as news, and
  so does a check that found nothing to start. The trigger need not be on in the
  project. The UI Bakery notes name `my progress` for this. Not changed: what
  each outcome of `my progress` starts, so a small and clear ticket still gets a
  report with the command and no development. Offered the choice to send such a
  ticket straight to development, the developer kept the report: "да гуд".
  Which triggers are on in a project plays no part for a ticket sent by hand:
  that only says what the script watches in the tracker.
- A project chat that was stopped comes back by itself. On 2026-11-25 the
  developer found the chat of `my-reviews` shown as "Remote Control
  disconnected": "опять сломалось что-то". That chat had been restored the
  evening before with `claude --bg --resume`, after the developer archived it by
  accident. `~/.claude/daemon.log` on the VM: Claude Code updated itself at 01:40
  UTC, and at 06:59 retired the chat (`bg retire 1b639043: idle-prompt, idle 8h,
  worker 2.1.331 (daemon 2.1.332)`); a review chat was retired the same way after
  eight idle hours. The script still took the chat for running, because Claude
  Code keeps listing it, so one line waited and no new chat took over. Now only
  a chat with a process counts as running, and the script wakes the chat on
  record of a project when it is listed with no process: at each reading of the
  tracker and before a line is sent, once an hour at most. Woken by hand that
  morning, the chat kept its row in the sidebar.
- Emphasis in the texts. The developer on 2026-11-25, with a screenshot of the
  text about a finished run: "еще в этих текстах (и во всех других) надо как-то
  акценты поставить маркдауном. а то тяжело читать". The Russian file now marks
  with bold where a ticket stands, the headings, and the labels ("Итог",
  "Нужно от тебя", "Отчёт"), and with italics the hints on what to write. The
  outcome of a step got a label of its own. A notification keeps plain text,
  and a title that is cut ends with "…". The English texts in the code stay
  plain: the developer's file decides the look.
- The look of the texts follows what the developer picked. On 2026-11-25 they
  were shown eight ways to format a message in the application and answered each:
  a quote block "не нравится. тускло", a GitHub callout "не красиво выглядит", a
  code block "для каких-то вещей может подойти но не очень", a table "норм норм",
  a rule "линия разделителя норм, можно юзать где-то", a task list and
  strikethrough "тоже хорошая тема", a collapsible block "не работает"; then
  "давай по моим комментам адаптируй шаблоны и ответы". The Russian file now
  prints a list of tickets as a table, triggers as a task list (ticked when on),
  the daily summary as a task list, a ticket that left struck through, and a rule
  before "Нужно от тебя", before the report, and before the line on when the
  tracker was read. The skill tells the project chat to use the same means in its
  own longer answers and none of the rejected ones.
- Triggers on the board: only those that are on, and nothing after the board.
  The developer on 2026-11-25, with a screenshot in which the trigger that was on
  stood ticked, grey, and struck through: "это странно выглядит. давай чтобы
  трикеры писалить без галочек и без зачеркиваний. и показывать только те тригеры
  что включены", and about the closing line "Дальше пришли номер тикета или скажи,
  какой триггер включить или выключить": "и этот текст в конце не нужен". The
  application draws a ticked item of a task list grey and struck through, so a
  tick now stands only for what is done. The board lists the triggers that are on
  as plain lines and ends with the line on when the tracker was read.
- No task lists and no struck-through text. The developer on 2026-11-25, with
  a screenshot of a project chat's own answer in which two ticked items stood grey
  and struck through: "и можно сделать список чтобы без зачеркийваний бл?
  невозможно читать". The application draws every ticked item that way, so the
  texts and the rule for the chat's own answers no longer use a task list, and a
  ticket that left is named with a bold word instead of being struck through.
  This takes back the task list and the strikethrough picked from the samples
  earlier that day.
- Ticket numbers in a report are links. The developer on 2026-11-25, with a
  screenshot of a report that began "UIB-6544, PR #7675 (автор AdamKorzun)": "и в
  отчетах можно сделать чтобы номера тикетов шли со ссылкой". The script does it
  when it copies a report to where the developer opens it, and in the verdict and
  the questions that it shows from the report: a number of a team whose tracker
  address it has seen becomes a link, while code, addresses, and existing links
  stay as they are. The filed report is not changed. `$project-scope` also asks
  the step to write the links itself.
- Screenshots that a report names can be opened. The developer on 2026-11-25,
  with a screenshot of a report that said "снимок `21-search-after-audit-logs.png`":
  "вот еще в отчетах есть картинки, и не понятно где их смотреть и как. мб можно
  вствалять как превью или опять же делать ссылкой?". The review had kept its
  screenshots in a folder of its own choice inside the project's folder
  (`evidence-UIB-6544/round-2`) and named them by file name only; the application
  opens no file outside a chat's folder. When the script copies a report for
  reading, it now copies each image or video that the report names and the
  project's folder holds next to the copy, makes the name a link, and the text
  about the report lists them as links. `$project-scope` tells a step to keep
  such files in `files/<ticket>/` of the project's folder. Not done: a preview
  inside the report, because it is not known whether the application draws an
  image in a file it shows.
- A ready report opens from the list. The developer the same day, with a
  screenshot of the list of tickets in review: "и вот еще мне отчет тут ссылкой
  не выдался". In a list, "report is ready" is now a link to the copy of the
  report in the chat's folder; before, only the text about one ticket linked it.
- A compacted project chat forgets finished tickets. The developer on
  2026-11-25: "для мастер агента я с ним могу общаться на счет тикетов и обсуждать
  реализци. и тд, и мне для старых тикетов это обсуждение не нужно будет уже. и
  можно было бы его выкинуть полность", and then: "надо сделать этот хук и конфиг
  так, чтобы они при инициализации проекта проверялись стоят или нет, и если нет —
  то ставились и работали бы именно для этих чатов". By the Claude Code
  documentation read that day, only a `PreCompact` hook steers an automatic
  compaction; it fires for a manual one too, and what it prints is added to the
  instructions for the summary. `agent-projects init` sets the hook when it is
  missing. The hook runs for every chat of the machine, and
  `agent-projects compact-hint` prints something only for a chat on record as a
  project's chat: keep the project, the developer's wishes, and the open
  questions and decisions of the tickets in work, which it lists from the
  script's own state; drop the rest. Codex has one compaction prompt for all
  chats of a machine, so it is left alone. Not checked: how closely a summary
  follows these instructions.
- A second run on one ticket says what it is. On 2026-11-25 a project chat showed
  the report of the development of UIB-6667 and, right under it, "разработка
  запускается" for the same ticket; the developer: "не понял тут ничего. 6667 тикет
  реализовали, что по нему еще раз запускается разработка?". It was a part they had
  asked for while the earlier run was going. `agent-projects watch add --about`
  now gives a run a few words that stand next to its step everywhere, and the
  skill has the chat say in one line of its own which request such a run carries
  out, and tell the developer at once when a request has to wait for a run.
- Each piece of news stands apart. The developer on 2026-11-25: "когда приходит
  новый ивент, то он смешивается в кашу с предыдущими и ничего не понятно. нужно
  какой-то хедер и футер", "ну и раделять сообщния по разным тикетам тоже стоит".
  Shown variants in the chat, they refused coloured marks ("иконки не нужно такие
  делать"), larger headings and blank space (the application draws a heading like
  bold text and collapses empty lines), a table as a frame, and a short form
  without the questions ("супер коротко тоже плохо"), and picked this: a rule
  before, between, and after the pieces of news; a bold first line with the
  ticket as a link, what happened, and how many answers wait; the title and a link
  to the pull request on the second line; the verdict; the questions in full; one
  last line with the report, the number of suggestions, and the words that open
  the agent's chat. "там где тикет нужны еще ссылки на тикеты, не забывай. и
  ссылки на пры если есть пр. вариант 2 мне больше нравится". No rules inside a
  piece any more.
- The board says what waits for the developer. On 2026-11-25, after
  `/project-master` printed a board with nothing under the trigger while a report
  with four questions stood above it: "я хочу чтобы если я выводил этот /project
  master то он как-то прошлые запросы на меня тоже выводил, вот выше есть что-то,
  что от меня нужно, и я бы хотел рефрешнуть командой и понять это". The board
  now lists each ticket whose last report in the project asks something, with the
  number of questions and a link to the report, until the ticket's history has a
  decision or a closing after that report. The chat records the decision when the
  developer answers.
- A button that opens the chat of the agent. The developer asked the same day
  for a button in the text about finished work, "чтобы я на неё нажал и
  автоматически в чат отправилось \"открой мне этого агента\"". The Claude Code
  documentation (remote-control, tools-reference, interactive-mode,
  cross-session-messaging, read the same day) gives a chat one thing that is a
  button: a question with options (`AskUserQuestion`). The project chat on the VM
  has that tool. Under Remote Control such a question stays open until it is
  answered, with no time limit, and the chat reads messages from other chats only
  between tool calls, so a question under every report would hold back the next
  news until the developer answers. No suggested replies and no link that sends
  text are documented. So the text about a report ends with the words to write,
  "open UIB-123", and no question is asked. The developer looked at a trial chat
  on the VM that showed such a text and decided: "кнопок нет. давай тогла без
  этого". No button is built.

- 2026-11-25, the news of tickets that came under a trigger or left it. The
  developer looked at one in the live chat ("слишком монго мусорного текста", and
  of the list of every ticket under the trigger: "«в ревью сейчас» тоже тупо") and
  picked from samples: a head "Триггер `my-review` · 2 новых, 1 закрыт" and under it
  one table with only the tickets that changed, with what happened and where each
  stands. Zero counts are not written, the project's name is not in the head, and
  the trigger's name stands in backticks ("давай тригер в ` ` обернем"). The
  heading over a trigger's tickets in the state of a project names the trigger the
  same way, so a trigger file has no `heading` any more.
- The same day: "я не получаю уведомления когда приходят эти ивенты о тригерах".
  This news asked for no notification; it now asks for one per trigger, such as
  "Триггер my-review: 1 новый".
- The same day, the state of a project ("вот тут еще что можно сделать"): the
  first line is a heading ("сделать больше хедингом мб"), the triggers that are on
  are a table ("про трикеры активные тоже таблицей"), a trigger with no tickets
  takes one line ("мб в одну строку"), and the Linear project is a link ("можно
  с сылку дать на проект в линерее"). The watching script asks Linear for that
  address once per project and keeps it in `watch.yaml` under `links`.

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
