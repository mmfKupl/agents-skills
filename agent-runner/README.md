# Codex agent runner

`agent-runner` is a foreground CLI for exactly one immutable YAML task. It starts one private Codex App Server through the stable Python SDK, or one headless Claude Code process when the task model starts with `claude-`, runs one ephemeral worker at a time, writes one unique YAML result, prints that result's absolute path to stdout, and exits. `agent-run-manifest` is a separate one-shot companion that initializes runs from the source chat invocation, applies a run-wide model ceiling, validates and registers immutable tasks, reconciles their results into a develop-task `run.yaml`, and finalizes the run. Launch separate runner processes for independent parallel work; there is no daemon, queue, scheduler, MCP server, or persistent conversation history.

## Install and run

Requirements: Python 3.10 or newer on POSIX and an installed `codex` CLI on `PATH`. Claude models also need the Claude Code CLI as `claude` on `PATH`, or its path in `AGENT_RUNNER_CLAUDE_BIN`. Advisory locking uses `fcntl`, so Windows is not supported.

```bash
python3.12 -m venv .venv
.venv/bin/pip install ./agent-runner
.venv/bin/agent-run-manifest init --workspace /absolute/worktree/path
# Use the printed run.yaml path in the following calls.
.venv/bin/agent-run-manifest new-job /absolute/path/to/run.yaml /absolute/path/to/task-draft.yaml \
  --role implementation-worker --contract-revision 1 --approved-by-preflight 001-preflight
.venv/bin/agent-runner /absolute/path/to/jobs/002-implementation/task.yaml
.venv/bin/agent-run-manifest reconcile /absolute/path/to/run.yaml
```

The Python dependencies are exactly `openai-codex==0.147.0` and `PyYAML==6.0.3`. Each invocation resolves `codex` from `PATH` and passes its absolute, resolved executable path to the SDK. Updating that CLI therefore updates the runtime used by subsequent runner jobs. The SDK's bundled runtime is not selected; a missing CLI produces a failed result with a clear error. The selected path is recorded as `runner.codex_bin`, and existing Codex authentication is reused. stdout contains only the absolute result path. Diagnostics go to stderr. Every successfully finalized, trustworthy result exits 0, regardless of its semantic status. Failure to create or finalize a reliable result exits 3. The YAML result—not the process exit code or console text—is the semantic source of truth.

The main agent or caller must place the task and its derived `results/` directory outside the target workspace and repository, normally under a private temporary job directory. The runner always derives results beside the supplied task and intentionally does not enforce that location policy.

## Task contract

Tasks are strict `agent-task` schema v2 YAML. Every shown field is required except `developer_instructions`. Unknown and duplicate keys are rejected. Strings marked nonempty may not contain only whitespace. Context token limits and attempts must be positive integers. The soft token limit must be 10% to 15% below the hard limit.

```yaml
kind: agent-task
schema_version: 2
job:
  id: fix-widget-test
  prompt: |
    Fix the failing widget unit test without changing the public API.
    Run the focused test and report its result.
workspace:
  cwd: /absolute/path/to/repository
agent:
  model: gpt-5.4
  reasoning_effort: high
  developer_instructions: "Preserve unrelated worktree changes."
permissions:
  sandbox_mode: read_only
  approval_policy: never
  network_access: false
supervision:
  context:
    soft_limit_tokens: 155000
    hard_limit_tokens: 180000
    checkpoint_grace_seconds: 30
  max_attempts: 3
```

The runner reads the original bytes once, records their SHA-256, and never rewrites the task. `workspace.cwd` must be an absolute existing directory. The optional `workspace.read_dirs` lists absolute existing directories outside the worktree that the job may read, such as the folder of screenshots a `visual-review` job inspects; the Claude engine passes each one as `--add-dir`. v2 always uses explicit deny-all approvals; it never silently approves or enables auto-review.

Supported permission combinations are:

| Sandbox | `network_access` | Meaning |
| --- | --- | --- |
| `read_only` | `false` | Safe default: filesystem read-only, network disabled |
| `workspace_write` | `false` | Workspace writes, network disabled by the preset |
| `danger_full_access` | `true` | Unsandboxed filesystem and network access |

Network-enabled `read_only` or `workspace_write`, and `danger_full_access` with claimed network denial, are rejected because the public SDK presets cannot faithfully enforce those combinations at both thread and turn boundaries. Full access is dangerous: it removes filesystem restrictions and necessarily permits network access. Use the read-only example unless the task genuinely needs more.

The only unconditional runtime override is `agents.enabled=false`. Every fresh thread is ephemeral and receives the task model, cwd, fixed no-delegation instructions, optional task developer instructions, mapped sandbox, and deny-all approval mode. The turn repeats the model, cwd, sandbox, deny-all mode, reasoning effort, and universal output schema instead of relying on SDK defaults.

## Worker output contract

Each worker must return one structured object. The SDK supplies it as JSON; the runner validates it and writes the converted object under YAML `outcome` or an attempt checkpoint.

```yaml
status: completed # completed | checkpoint | blocked
summary: Focused summary
report: Detailed handoff for the main agent
completed: [Implemented the requested change]
remaining: []
changed_files: [src/widget.py]
artifacts: []
validation:
  - command: python -m unittest tests.test_widget
    status: passed
    summary: 8 tests passed
warnings: []
questions: []
```

All keys are required, no extra keys are allowed, string-array elements must be strings, and each validation entry contains exactly `command`, `status`, and `summary` strings.

## Result contract

For `/path/to/task.yaml`, every invocation creates a different `/path/to/results/<execution-id>.yaml`, and `<execution-id>.events.jsonl` next to it with the job's messages and tool calls (mode `0600`; it may contain file contents). It first writes status `running`, then rewrites the same result atomically using a same-directory temporary file, file `fsync`, `os.replace`, and directory `fsync`. Milestones and usage events are persisted immediately; noisy progress events use a rate-limited heartbeat. Lock files are always external, but avoiding result artifacts in the repository depends on the caller placing the task outside it as required above.

```yaml
kind: agent-result
schema_version: 1
execution:
  id: 20260818T120000000000Z-12345-a1b2c3d4e5f6
  status: completed
  pid: 12345
  started_at: '2026-08-18T12:00:00.000Z'
  finished_at: '2026-08-18T12:01:00.000Z'
  heartbeat_at: '2026-08-18T12:01:00.000Z'
task:
  path: /path/to/task.yaml
  sha256: 64-hex-digest
  job_id: fix-widget-test
runner:
  version: 1.8.5
  sdk_version: 0.147.0
  sdk_package: openai-codex
  codex_bin: /absolute/path/to/codex
  python_version: 3.12.13
  pyyaml_version: 6.0.3
effective_configuration: {}
attempts: []
usage:
  input_tokens: 0
  cached_input_tokens: 0
  cache_write_input_tokens: 0
  output_tokens: 0
  reasoning_output_tokens: 0
  total_tokens: 0
outcome: null
approval:
  policy: never
  mode: deny_all
  requested: false
error: null
```

Attempts record fresh thread and turn IDs, timestamps, status, peak observed context tokens, an optional percentage diagnostic when the model reports its window, last and total token usage, and a structured checkpoint or fallback partial output when rotation is needed. Top-level usage sums the final per-attempt totals. Terminal statuses are `completed`, `blocked`, `failed`, `interrupted`, `worktree_locked`, `invalid_task`, and `context_exhausted`. `needs_approval` is reserved for future schemas and is unreachable under v2 deny-all policy.

## Claude Code engine

A task whose `agent.model` starts with `claude-` (for example `claude-opus-5-5`) runs through `claude -p` instead of the Codex SDK. The task schema, result schema, worktree lock, and exit codes are the same, so `agent-run-manifest` registers and reconciles these jobs like any other.

The runner passes the model, the effort, the fixed and task developer instructions (`--append-system-prompt`), and the universal output schema (`--json-schema`). It always adds `--permission-prompts none`, `--strict-mcp-config`, and `--no-session-persistence`. The prompt goes to stdin. Claude Code file tools have no OS sandbox, so each permission mode limits the tool list and runs Bash in Claude's own sandbox:

| Sandbox | Tools | Permission mode | Bash sandbox |
| --- | --- | --- | --- |
| `read_only` | Read, Grep, Glob, Bash | `dontAsk` | on, the Git worktree root (or working directory outside Git) write-denied by absolute path, network blocked |
| `workspace_write` | adds Edit, Write, NotebookEdit | `acceptEdits` | on, writes limited to the working directory, network blocked |
| `danger_full_access` | adds WebFetch, WebSearch | `bypassPermissions` | off |

The sandbox uses `failIfUnavailable: true` and `allowUnsandboxedCommands: false`: where it cannot start (for example Linux without bubblewrap), the job fails instead of running unsandboxed. User and project settings, hooks, and `CLAUDE.md` still load; MCP servers do not.

Claude Code compacts its own context, so these jobs have one attempt and no context rotation; `supervision.context` is recorded but not enforced. A returned `checkpoint` status fails the job. Usage follows the Codex convention: `input_tokens` is uncached input plus cache reads plus cache writes, `cached_input_tokens` is cache reads, `cache_write_input_tokens` is cache writes, and `reasoning_output_tokens` is thinking tokens. The attempt's `thread_id` is the Claude session ID, and `runner.claude_bin` records the CLI path. On SIGINT or SIGTERM the runner forwards SIGINT to the CLI's process group, kills it after the cleanup grace period, and finalizes `interrupted`.

## Context rotation, signals, and cleanup

The runner observes public `thread/tokenUsage/updated` stream events. Accumulated thread totals and the reported model context window are diagnostic only. At the absolute soft token limit it steers once for a structured checkpoint. At the absolute hard token limit, or after checkpoint grace expires, it interrupts and waits for the old turn to become terminal before starting a fresh ephemeral thread. Only the task, fixed instructions, and the structured checkpoint (or fallback partial agent output) cross the boundary; dialogue history does not.

The terminal SDK turn status is authoritative. Structured output can complete or block a run only when the turn itself completed. A failed turn remains failed even if it emitted valid JSON first. A context-interrupted turn can contribute a valid checkpoint only as carry into a fresh attempt.

Thresholds are best-effort at SDK event boundaries. A model may emit a usage event after it has crossed a token threshold. Rotation uses the latest turn's absolute `total_tokens` and does not depend on the model's reported context-window size. The runner deliberately has no wall-clock job timeout; a foreground invocation waits until the worker finishes, exhausts its context attempts, fails, or receives SIGINT/SIGTERM. On those signals it requests interruption for an active turn, waits a bounded cleanup interval, closes the SDK/private App Server, and finalizes the result when possible. SIGKILL, power loss, or host failure can leave a valid `running` result because no process can perform cleanup afterward.

## Concurrency and locking

Read-only runs take no lock and can overlap. `workspace_write` and `danger_full_access` take a nonblocking POSIX advisory lock keyed by the canonical Git worktree root, falling back to canonical cwd outside Git. Lock files live under the platform temporary directory. A conflict produces `worktree_locked`. The lock only coordinates cooperating agent-runner processes; it does not stop editors, Git commands, or other programs.

## Run manifest companion

`agent-run-manifest` operates on a strict `develop-task-run` schema v1 `run.yaml`.
Run `init --workspace /absolute/worktree/path` from the main Codex chat. It creates
a unique platform-temporary directory with mode `0700` and prints its absolute
manifest path. No App Server is started by the helper.

`init` reads the latest unquoted develop-task invocation from the user messages
in every rollout matching `CODEX_THREAD_ID` under the configured Codex home.
Codex may create another matching rollout after compaction; this is normal and
does not require deleting or moving session files. The helper orders candidates
by their event timestamps, ignores injected skills/context, fenced code, inline
code, and block quotes, and pins the selected message and turn. Both
`$develop-task` / `develop-task` and the Markdown skill-link form work.
Parameters immediately after the skill name are authoritative:

- `D`: optional compatibility alias for the single default matrix. Place it
  before a ceiling, for example `$develop-task D M`. A mode is removed and
  rejected before run creation;
- `M` / `main_ceiling` uses the supported model recorded in that invocation's
  `turn_context`, not a later turn's model;
- `E Luna`, `E: Sol`, `E Astra`, or `explicit_ceiling gpt-6.2-sol` selects the
  named ceiling;
- no restriction keeps `adaptive`.

Supported ceilings follow this order: `gpt-6-luna`, `gpt-6.1-terra`,
`gpt-6-sol`, `gpt-6.1-sol`, `gpt-6.2-sol`, `gpt-6-astra`, `gpt-6.2-astra`. Claude
models share their GPT peer's rank: `claude-haiku-5-5` = Luna, `claude-sonnet-5-5` =
Terra, `claude-opus-5-5` = GPT-6.2 Sol, `claude-fable-5-2` = GPT-6.2 Astra (`claude-fable-5-1`
keeps that rank for `M` and older runs). Short names
(`Luna`, `Terra`, `Sol`, `Astra`, `Haiku`, `Sonnet`, `Opus`, `Fable`) resolve
to these IDs. A capped job keeps its vendor: it gets that vendor's strongest
model at or below the ceiling's rank, so `E Terra` caps `claude-opus-5-5` to
`claude-sonnet-5-5`, and `gpt-6-sol` or `gpt-6.1-sol` caps it to Sonnet as well.
Sol resolves to `gpt-6.2-sol` and Astra to `gpt-6.2-astra` for new runs; use a full
earlier ID such as `gpt-6.1-sol` for an earlier-generation ceiling. Existing pinned Sol
and Astra ceilings retain their recorded model. Full GPT-5.6 IDs, including `gpt-5.6-terra`, are rejected for new runs
and jobs.

Main still interprets natural-language constraints. It may pass
`--mode main_ceiling`, or `--mode explicit_ceiling --maximum-model Luna` with
the contextually selected model. These options cannot override explicit M/E
parameters with or without the optional D prefix.
Ambiguous/missing source, unknown ceiling, and conflicting options fail before
creating a run. `current-model` remains a diagnostic for the latest model, not
the source-turn snapshot.

New runs record `run.routing_matrix: D`, `run.model_policy`
(`mode`, `maximum_model`) and
`run.model_policy_source` (`thread_id`, `turn_id`, `message_sha256`). The source
identifies the original user message without copying the chat into the manifest.
Every `new-job` re-reads that source and verifies the matrix, explicit
parameters, and the invocation model before dispatch; editing `M` to `adaptive` fails. Later user
messages, model changes, and `resume` do not replace the pinned source. Free-form
language interpretation remains main's responsibility, not a natural-language
parser in the helper. This protects the normal helper path, not arbitrary direct
runner or native-subagent calls that bypass it.

Historical A manifests remain readable for reconciliation and usage, but cannot
dispatch new jobs. Legacy manifests remain readable, with missing matrix
interpreted as D and missing policy as `adaptive` for reconciliation. To add a
job to a legacy/manual manifest without a source,
`new-job` first performs the same source check from the calling chat and records
the source only if its existing matrix and policy agree. Missing fields cannot
bypass a source M/E ceiling; no worker starts on a mismatch or
unavailable source.

`new-job` also validates a complete `agent-task` v2 draft, requires its workspace
to match the run, caps the requested model when needed, creates the final immutable
`jobs/<job.id>/task.yaml`, and atomically registers the pending entry. Each job
records `requested_model`, `selected_model`, and `limited_by`; the legacy `model`
field equals `selected_model`. Its stdout is the final task path. The companion
later scans that task's sibling `results/` directory, verifies the task path,
SHA-256, job ID, result schema, and execution status, then copies only
`result_path`, `status`, `execution_id`, and `usage` into the job entry.

Use exactly one job directory per runner invocation. Reconciliation rejects multiple result files for one job instead of guessing which execution is authoritative. Updates take a short `fcntl` lock beside `run.yaml` and use a same-directory temporary file, file `fsync`, `os.replace`, and directory `fsync`.

Optional `run.requirements` stores a `revision` and an `amendments` list. Missing
state means revision 1 with no amendments. `new-job` records that revision as
`requirements_revision`, separately from its implementation `contract_revision`.
Existing jobs without the new field remain readable. To record an explicit
developer decision, use:

```bash
agent-run-manifest amend-requirement /absolute/path/to/run.yaml R1 \
  --before 'Temporary report files are permitted with cleanup.' \
  --after 'Generate the report only in memory.' \
  --source 'Developer message <reference>: generate it only in memory.' \
  --reason 'The developer requested no temporary report files.'
```

The command atomically appends the five supplied nonempty strings plus the next
revision, and advances the run's requirements revision. Revisions start at 1
and advance once per amendment. It preserves old jobs and immutable task/result
files. It validates the journal's structure, not the authenticity or meaning
of the developer decision. Exact requirements and per-cycle coverage belong in
the task's `job.prompt` and result's `outcome.report`; the generic runner and
their schemas are unchanged. Stop affected workers before amending, and resume
a terminal run first.

```bash
agent-run-manifest init --workspace /absolute/worktree/path
# Use the printed path below, including for M/E runs; do not hand-write run.yaml.
agent-run-manifest new-job /absolute/path/to/run.yaml /absolute/path/to/task-draft.yaml \
  --role implementation-worker \
  --contract-revision 1 \
  --approved-by-preflight 001-preflight
agent-run-manifest reconcile /absolute/path/to/run.yaml
agent-run-manifest finish /absolute/path/to/run.yaml completed
agent-run-manifest resume /absolute/path/to/run.yaml
```

Do not manually create final job directories or append manifest entries. Omit
`--approved-by-preflight` for the initial preflight. `finish` first reconciles
and refuses to close a run with any `pending` or `running` job or any
unregistered `jobs/*/task.yaml`. Terminal run statuses are `completed`,
`blocked`, `needs_user_input`, and `stopped`. `resume` reconciles, resets the run
to `running`, and clears `finished_at`. The helper does not interpret gate
reports or decide whether earlier failed jobs were semantically resolved.

Matrix selection is pinned independently of the model ceiling. The manifest
helper does not choose a semantic role/profile route; main supplies the
requested model/effort from the default matrix before the helper caps it.
Usage summaries
come from existing job results: count each attempt once, distinguish unavailable
zero-initialized counters from measured usage, and keep the manifest path out of
user-facing handoff/final reports. See develop-task for the report requirements.

## Project checks and full chats

Two commands serve project triggers (`planning/project-master.md`). Neither needs a
run manifest.

A **check** is an ordinary read-only job with the role `project-check`. It sorts one
tracker event into one outcome of a trigger. It runs on the cheapest model whatever
the profile, unless `--model` names another one; `--model` accepts short names such
as `haiku` or `Sol`. The summary carries `check_outcome`, read from the `outcome:`
line of the report, so a script can branch without reading the report. Like every
job it has no tracker and no network: the caller puts the event, the ticket's
history, and the ticket's local record into the packet.

```bash
agent-run-manifest dispatch --no-manifest --workspace /absolute/repository \
  --role project-check --profile fast --vendor claude --prompt-file /absolute/packet.md
```

A **chat** is the opposite of a job: the application's normal session, with its
skills and connections, kept so that it can be continued after a person answers.
Use it to run a whole skill.

```bash
agent-run-manifest chat --workspace /absolute/repository --model opus --effort high \
  --prompt-file /absolute/prompt.md --run-dir /absolute/run --worktree uib-123-review
agent-run-manifest chat-resume /absolute/run --prompt-file /absolute/answer.md
```

- `--vendor auto`, the default, follows the model's own name: a Claude name starts
  `claude -p`, any other starts `codex exec`. `--vendor claude` or `--vendor codex`
  moves the model to its peer on that vendor. Set `AGENT_RUNNER_CLAUDE_BIN` or
  `AGENT_RUNNER_CODEX_BIN` when the application is not on `PATH`.
- `--worktree <name>` gives the chat a working copy of its own. Claude Code makes it
  in `.claude/worktrees/<name>` and leaves it locked when the turn ends; remove it
  with `git worktree unlock` and `git worktree remove`. Codex makes a managed one,
  ignores the name, and does not print its path: the command takes the working copy
  that appeared during the first turn. Later turns run in that copy.
- Permissions are the application's own defaults on that machine. `--unrestricted`
  turns approvals and the sandbox off, only when the user allowed it.
- The prompt goes to standard input. A chat started this way does not appear in the
  Claude sidebar.
- `--run-dir` holds `chat.yaml` and, for every turn, the prompt, the final message,
  the raw output, and the error output. Without it the command makes a temporary
  folder. One turn runs at a time per chat.
- The command prints a summary with `status` (`completed`, `failed`, or `timed_out`),
  `session`, `usage` in the same convention as a job, `cost_usd` when the application
  reports it, and the final message as `report`. It exits with 0 only for
  `completed`. `--timeout-minutes`, 180 by default, stops a turn that runs too long.

## Watching and triggers

`agent-projects` also watches the tracker for the triggers that projects turned on
(`planning/project-master.md`, section "Triggers"). No model takes part: a loop reads
Linear, matches what it finds against the trigger files, and starts a full chat with
`agent-run-manifest chat` for each match.

```bash
agent-projects trigger list                          # every trigger here, in plain words
agent-projects trigger list --project billing        # split into on and off for a project
agent-projects trigger check /absolute/trigger.yaml  # does the script accept this file
agent-projects project triggers billing --on "my review"
agent-projects watch poll                            # read Linear once; starts nothing
agent-projects watch list                            # events that are not over
agent-projects watch start 3 4                       # let the loop start held events
agent-projects watch add billing UIB-123 <<'EOF'     # queue a step the developer asked for
$review-task UIB-123
EOF
agent-projects board billing                         # the state of the project, as text to show as it is
agent-projects board billing UIB-123                 # one ticket in full, with its last report
agent-projects news billing                          # what happened since the project chat last asked
agent-projects watch dismiss 5
agent-projects watch limit 3                         # how many runs may go at once
agent-projects watch digest --at 09:00 --timezone Europe/Warsaw   # daily summary; --off
agent-projects watch install                         # keep the loop running (systemd)
agent-projects pause                                 # and: agent-projects resume
```

`board` and `news` print text that a project chat shows the developer as it is, and
each command that changes something answers with such a line under `say`. The English
texts are in `project_messages.py`. `skills/project-master/messages.yaml` replaces
them with the developer's own language, and `messages.yaml` in the projects folder of
a machine wins over both. A text that names a slot the scripts do not fill is left
out, and `agent-projects init` says so under `messages`. What follows the line
`=== for the chat, not for the developer ===` is for the chat: commands to start or
stop, and the notification to send.

- The format of a trigger file is in `skills/project-master/references/triggers.md`.
- Triggers are read from `agent-projects/triggers/` on the machine, then from
  `skills/project-master/triggers/` as installed for Claude Code and for Codex. A trigger
  on the machine wins over a ready one with the same name. A file with anything the
  script does not understand is refused whole and reported as a problem, so that a
  misspelled condition never widens what a trigger starts.
- The loop reads Linear every ten minutes; `watch run --interval <seconds>` changes
  that. Starting what waits and closing what ended need only local files, so the loop
  does them every minute. Nothing from Linear is stored except the matches, in
  `agent-projects/watch.yaml`.
- For each project that has triggers on, the loop asks Linear for the tickets of that
  project's scope, so a match belongs to the project it was asked for. A ticket goes
  to one project per trigger: the project that names the ticket by number wins over
  one that covers a whole Linear project, and otherwise the first project by name
  gets it.
- An entry reads one of three events: a Linear status change, a Linear comment, or a
  review or comment on the ticket's pull request. A status change is judged by
  where a ticket is now: the ticket is in the trigger's status, and the move that put
  it there fits the entry (`from`, `actor`), as does the ticket's assignee. One move
  counts once, so a ticket that leaves the status and comes back counts again. The
  move is looked for in the ticket's last 25 changes.
- Comments are read only for tickets that a chat on this machine reviewed or worked
  on, taken from the ticket records, and that are still open. The pull request is
  the GitHub link Linear holds for the ticket, read through `gh`. A comment counts
  from the moment its trigger was turned on, once, and the comments that came in
  since the last reading of a ticket are one event. Agent reports (`$develop-please:`),
  bot commands (`/e2e-preview`), and bots are left out when the entry says
  `skip: agent_comment`. Such a ticket goes to the project where a chat worked on it,
  else to the one that names it, else to the one that covers its Linear project.
- An entry with no `then` goes through the trigger's `check`: the loop writes a packet
  (the event, the ticket, its status history, its record here, the last report) and
  runs the read-only role `project-check` on the check's model. The outcome it picks
  names the run. A run with `quiet: true` only records something, so the project chat
  is not told when it ends. An outcome that is `skip` starts nothing; an answer that is no
  outcome of the trigger fails the event, and `watch start` sends it to the check
  again. The packet and the answer are in `runs/<date>-<ticket>-check-<id>`.
- A move is acted on only after two minutes, so that a chat that took the ticket has
  written its record. A ticket that a chat on this machine holds is recorded as
  `skipped`.
- The first poll after a trigger is turned on, and the first after `resume`, start
  nothing: what matches is recorded as `held`, and `watch start` or `watch dismiss`
  decides. Later matches are `waiting`, and the loop starts them within a minute.
- A run is `agent-run-manifest chat` with the prompt
  `/project-scope <project> <the trigger's command>` (`$` instead of `/` under Codex),
  in a working copy of its own, with approvals off, because nobody is there to
  approve. Its folder is `agent-projects/project-<name>/runs/<date>-<ticket>-<run>-<id>`,
  which `chat-resume` takes when the developer answers a question. The run files its
  report; it does not message the project chat. When the run ends, the loop builds
  one line (the report is ready, the run failed, or it ended without a report) and
  starts a small chat on the cheapest model whose only job is to send that line to
  the project chat. A script cannot message a chat itself, and a run on a cheap model
  may skip the step.
- A run's working copy stays while its ticket is open, because the run may be
  continued with an answer. Once the ticket is Done, Canceled, Won't do, or Duplicate
  in Linear, the next reading removes the copy and its branch. A copy with changes
  that are not committed is kept and named in `watch list --all`.
- `watch install` writes a systemd user service that survives a logout when lingering
  is on for the user. `scripts/install-skills.sh` restarts it; the runs it started
  keep going. Elsewhere, keep `agent-projects watch run` running yourself.
- The loop is built to keep going. `watch.yaml` is saved even when a round fails, so
  a chat that was started is never started twice. An error on one event fails that
  event, with the reason in its note, and the others go on. A run that ends gives its
  ticket back when it did not. An event whose check or run can no longer be reached
  is freed with `watch dismiss`. After a restart of the machine a process number is
  trusted only when its command line names the run's folder.
- Names of people and statuses from the tracker are reduced to plain words before
  they go into a prompt, and the text of a ticket or comment reaches only the check,
  between fences that hold a random word. Working copies are removed only when they
  are named after the run, which is true for Claude Code and not for Codex.
- The events that wait are a queue. The loop starts the oldest first, and only while
  fewer than the limit run: three unless `watch limit <n>` says otherwise. Checks
  have a queue of their own with the same limit. A reading that adds more events
  than the limit also sends the project chat one line, so that the developer can
  drop part of a burst.
- Before a line goes to a project chat, the loop lists the chats that run on the
  machine (`claude agents --json`). When the project's chat is not among them, the
  line is kept (`undelivered` in `agent-projects status`), and the loop starts a
  visible chat with Remote Control and the fixed text `/project-master <project>`,
  at most once in six hours per project. That chat records itself as the project's
  chat; five minutes later the loop sends it the lines that waited, and it notifies
  the developer. News is never put into the text that starts a chat.
- `watch digest --at <HH:MM> [--timezone <name>]` turns on a daily summary: after
  that time of day, each project whose runs did something gets one message with
  what finished, what failed, what waits for the developer, and what the runs cost.
- An event that has been over for thirty days is forgotten with its folders; its key
  stays, so the same move or comment is not taken for news again. Old message
  folders go the same way.
- `ticket take` remembers a working copy that Claude Code made for the chat
  (`.claude/worktrees/<name>`). Once the ticket is closed, nobody holds it, and the
  chat that made the copy no longer runs, the loop removes the copy, without force.
  A copy named `bridge-...` belongs to a chat made from the Claude app and is left
  to the app.
- A project has `section: true` unless it was made with `project create --no-section`
  or turned off with `agent-projects project section <name> off`. The script does
  nothing with it: the skills read it and have each chat of the project file itself
  into a sidebar section named after the project.
- `pause` creates `agent-projects/paused`. While it is there, nothing is read from
  the tracker and nothing starts; runs already going finish.
- The Linear key is read from `~/.config/agent-projects/linear-api-key`
  (`AGENT_PROJECTS_LINEAR_KEY_FILE` names another file) and goes only into the request
  header. `agent-projects init` says whether Linear answers and whether the loop runs.
