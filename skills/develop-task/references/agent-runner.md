# Agent Runner Backend

Read this completely when the backend is `runner`, and before the first other-vendor
job under Cross-Vendor Review. Without the runner backend, use the sections on the
command, task, role contracts, permissions, other-vendor jobs, supervision budgets,
and execution, and skip every `agent-run-manifest` step.

## Resolve The Command

Resolve one executable once per run, in this order:

1. an exact path the user supplied;
2. the nonempty `CODEX_AGENT_RUNNER` environment variable;
3. `${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-runner`;
4. `agent-runner` from `PATH`.

Require `agent-runner --help` to succeed before preflight. Do not install, upgrade, or
repair the runner from inside the workflow. If none is available, fail closed and
report it; only an explicit user instruction selects direct subagents.

Resolve `agent-run-manifest` from the same directory, then from `PATH`, and require
its `--help` to succeed before creating `run.yaml`.

## Initialize The Run And Model Policy

Once the target worktree is known, before the first job:

```bash
agent-run-manifest init --workspace /absolute/worktree/path
```

Check its exit status before using the output: on failure it prints nothing, and a
later `sed` or `cat` on the empty path waits on stdin forever. On success it prints
only the absolute `run.yaml` path, in a new private temporary directory (mode `0700`,
outside the repository). Keep that path for later calls.

`init` reads the latest unquoted develop-task invocation from real user messages, in
every rollout for `CODEX_THREAD_ID` or in Claude Code the transcript for
`CLAUDE_CODE_SESSION_ID`. Never delete or move those files. It resolves parameters
right after the skill name:

- `D`: optional alias for the single matrix, placed before a ceiling (`$develop-task
  D M`). Mode `A` is rejected;
- `M` / `main_ceiling`: pins the model of the invocation turn, not of a later one;
- `E Luna`, `E: Sol`, `E Opus`, or `explicit_ceiling gpt-6.1-sol`: pins the named model;
- none: `adaptive`.

For a plain-language limit, main interprets it and passes `--mode main_ceiling` or
`--mode explicit_ceiling --maximum-model Luna`. These cannot contradict explicit
parameters; do not pass an invented or default policy over a recognized alias. Read the
generated policy and report it before the first job. A missing source, ambiguous
invocation, unsupported ceiling, or conflict fails before the run exists: recover the
evidence, not an unconstrained substitute. `current-model` is diagnostic only.

## Run Directory And Ownership

```text
<temporary-root>/codex-agent-run-<unique-id>/
├── run.yaml
└── jobs/<job.id>/
    ├── task.yaml
    └── results/<execution-id>.yaml, <execution-id>.events.jsonl
```

The helper owns `run.yaml` and its lifecycle timestamps; never hand-write it, append
job entries, or create final job directories. Its fields are in
[`run-manifest-schema.md`](run-manifest-schema.md), read only when you need one. Main prepares each task and owns the job plan. The runner alone creates
result files. Workers must not receive orchestration paths or edit orchestration files.

The `.events.jsonl` file is the job's own log of messages and tool calls, for diagnosing
why a job stopped. It may contain file contents; keep it in the run directory and do not
copy it into reports.

Give each `job.id` a rising sequence and a short role slug, such as
`002-implementation`; `new-job` creates its directory. A task is immutable once its process starts. Every retry, gate
challenge, specialist interpretation, postflight cycle, or writer fix gets a new job.

The matrix, policy, and their source are fixed for the run, including retries and
resumes; `new-job` rejects a contradiction. Do not copy a manifest to another chat to
bypass this. Older manifests stay readable: no `routing_matrix` means D, historical A
runs cannot dispatch, a job added to one without a source gets the same check first, and
no `requirements` means revision 1 with no amendments, without certifying old jobs.

Prepare each strict task YAML at a temporary path outside `jobs/`, then register it:

```bash
agent-run-manifest new-job /absolute/path/to/run.yaml /absolute/path/to/task-draft.yaml \
  --role implementation-worker \
  --contract-revision 1 \
  --approved-by-preflight 001-preflight
```

Omit `--approved-by-preflight` for the initial preflight. The command validates the task,
requires its workspace to match the run, verifies the policy source, applies the ceiling,
creates `jobs/<job.id>/task.yaml`, records the current `requirements_revision`, and prints
the final task path. When capped, the task holds the selected model and the manifest
records requested model, selected model, and limiting mode.

After each process, run `agent-run-manifest reconcile <run.yaml>`; never hand-copy its
result path, status, ID, or usage. Keep full reports in result files, not in `run.yaml`.

Start at `contract_revision: 1` and increment it before every fresh preflight for a
`substantive` or `replan` fix; `mechanical` and `reduction` fixes stay on it. Preflight
jobs have `approved_by_preflight: null`. Every implementation and postflight job names
the exact approving preflight, even when role, model, or writer continues. Other gate or
specialist follow-ups record the current revision and that preflight when one exists.

## Record Approved Requirement Changes

Main must recover an actual explicit developer decision first; a gate conclusion,
existing code, or a claim that the ticket is stale is not enough. Stop any affected
writer. If the run is terminal, resume it. Then:

```bash
agent-run-manifest amend-requirement /absolute/path/to/run.yaml R1 \
  --before 'Temporary report files are allowed with cleanup.' \
  --after 'Generate reports only in memory.' \
  --source 'Developer message <reference>: "Generate reports only in memory."' \
  --reason 'The developer requested no temporary report files.'
```

Use the exact wording and the real message or comment reference, and the developer's
reason, or say none was given. One amendment advances one revision; code fixes and fresh
preflights do not. The helper checks structure, not whether the source is genuine.

Keep old task and result files intact and do not rewrite history. New jobs get the
original excerpts and confirmed amendments in their prompts. State in the next packet when
the ticket text still differs from the confirmed decision.

## Create One Task

Prepare exactly one strict `agent-task` v2 document per invocation:

```yaml
kind: agent-task
schema_version: 2
job:
  id: 001-preflight
  prompt: |
    <self-contained task packet and exact role-specific inputs>
workspace:
  cwd: /absolute/worktree/path
agent:
  model: gpt-6.1-sol
  reasoning_effort: high
  developer_instructions: |
    <role contract plus runner output-envelope instructions>
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

Every field is required except `agent.developer_instructions`, which this workflow always
supplies. Use absolute existing paths. Put the adaptive requested model and approved
effort in the draft; `new-job` applies any ceiling.

Inside `job.prompt`, include the routing matrix and applicable routing rules, requirements
revision, contract revision, and for implementation and postflight the approving preflight
job ID, plus requirement IDs, exact excerpts, source references, and confirmed amendments
kept apart from main's hypothesis. Final postflight needs the complete requirement set. Add
no unsupported keys to the document.

## Role Contracts And Output Envelope

Supported roles: `preflight-review`, `implementation-worker`, `postflight-review`,
`repo-practice-review`, `best-practice-review`, `test-review`, `code-simplicity-review`,
and `diagnosis-review`.

Composed discovery uses these specialist roles before initial preflight, with no approving
preflight. Final review-task checks belong in a fresh `postflight-review` packet. Create no
nested runs, skill-name roles, or extra schema fields. Model selection and the review-round
count stay with main.

`${CODEX_HOME:-$HOME/.codex}/agents/<role>.toml` is the canonical role contract. Put its
complete `developer_instructions` in the task. If the file is unavailable, fail that role
closed rather than reconstructing it from memory. Append to every role contract:

```text
The runner requires one universal structured output object. Perform the role
contract exactly, but place its complete required role response inside the
universal `report` string. Use `summary` for a short semantic summary and the
remaining universal fields for evidence, validation, warnings, and questions.
The universal status describes job execution, not the role decision:
- use `completed` when the role produced its decision/report, including
  preflight revise/blocked decisions and postflight Approval: no;
- use `blocked` only when the role itself could not execute;
- use `checkpoint` only when instructed by the runner for context rotation.
Do not create subagents or delegate.
```

For `implementation-worker`, role status `implemented` is universal `completed`;
`replan_required` and `blocked` are universal `blocked`, with the exact role status and
explanation in `report`.

Main interprets the role report. Runner `completed` never means preflight approval,
postflight approval, or successful implementation. Each cycle's `Requirements coverage`
goes inside `outcome.report`, with no added envelope fields; the runner does not interpret
requirements.

## Permission Mapping

Use only these combinations, always with `approval_policy: never`:

| Job | sandbox_mode | network_access |
| --- | --- | --- |
| Every review or specialist | `read_only` | `false` |
| Normal implementation | `workspace_write` | `false` |
| Implementation when the root run is explicitly unrestricted | `danger_full_access` | `true` |

Never broaden a job to full access merely because it needs network or an approval. If a
safe task needs an unsupported combination, stop and ask the user to change the task,
select direct subagents, or authorize unrestricted execution. The runner cannot pause for
approval: a denied operation is a result main must surface, and it is not retried with
broader permissions without a new user decision.

## Other-Vendor Jobs

A task whose `agent.model` starts with `claude-` runs through the runner's Claude Code
engine; every other model runs through Codex. Schemas, the permission table, the worktree
lock, and result interpretation are the same. Differences:

- the Claude engine needs a signed-in `claude` CLI on `PATH` or in
  `AGENT_RUNNER_CLAUDE_BIN`;
- Bash runs in Claude's own sandbox; if it cannot start (for example on Linux without
  bubblewrap), the job fails instead of running unsandboxed;
- a Claude job has one attempt and no context rotation; its budget is recorded, not
  enforced;
- a read-only Claude job can run Bash in the sandbox, which blocks writes and network; a
  compound command may be denied, so keep commands simple;
- `input_tokens` includes cache reads and writes, which are also reported separately.

Run `agent-runner` outside the Codex sandbox: both engines need network access, and Claude's
sandbox may fail to start inside another one.

Without the runner backend, prepare the task as under Create One Task with the selected
model after the ceiling, write it to `<private-temp-dir>/<job-id>/task.yaml` with mode `0700`
on the directory, run `agent-runner` on that path, and read its single result under
`results/`. Do not call `agent-run-manifest`. Report usage from the result file.

## Supervision Budgets

| Profile | soft | hard | grace seconds | attempts |
| --- | ---: | ---: | ---: | ---: |
| Fast | 155,000 tokens | 180,000 tokens | 20 | 2 |
| Standard | 155,000 tokens | 180,000 tokens | 30 | 3 |
| Deep | 210,000 tokens | 240,000 tokens | 45 | 4 |
| Critical | 350,000 tokens | 400,000 tokens | 60 | 5 |
| Exceptional | 220,000 tokens | 250,000 tokens | 60 | 5 |

Exceptional raises the reasoning tier, not the job size: keep an Astra job bounded and
split separable responsibilities before preflight. Specialists use the requesting gate's
profile. A changed profile or a materially larger packet needs a new preflight decision.
These limits control the latest turn's context, not cumulative usage. Runner jobs have no
wall-clock timeout; the caller may stop one with SIGINT or SIGTERM.

## Execute, Wait, And Interpret

Invoke the command in the foreground with the one task path. On exit, stdout holds one
absolute result path; silence until then is expected. Apply the Silent Long-Poll Discipline.

When the host exposes the `functions.exec` wrapper, start the invocation with this first
line so the outer cell uses the same wait:

```javascript
// @exec: {"yield_time_ms": 300000}
```

The transport may yield before the runner exits. Treat that as transport, not a job event,
and stay on the same handle with the longest accepted wait, up to `yield_time_ms: 300000`:
`write_stdin` with empty `chars` for a `session_id`, or `functions.wait` for a `cell_id`
("Script running with cell ID ..."). Repeat silently until the terminal result, and do
not read partial result YAML, repository state, or runner-owned files during the wait.

The exit code reports transport, not semantic success:

- `0`: a trustworthy result was finalized; inspect it;
- nonzero: no reliable result is guaranteed; stop the job and report stderr plus any safely
  discoverable running artifact.

Validate the result kind/schema, task path/hash, and terminal status before using the
report. Then:

- `completed`: interpret `outcome.report` by the role contract;
- `blocked`: interpret the report and stop or replan as required;
- `failed`, `interrupted`, `context_exhausted`: keep the artifact and decide whether the
  evidence permits a new job;
- `worktree_locked`: do not bypass the lock; wait for the known owner or stop with the conflict;
- `invalid_task`: correct main-owned YAML in a new job directory;
- `needs_approval`: reserved; stop for user input.

In runner mode, reconcile after validating and read the job entry before creating another
job. A reconciliation failure is an orchestration error: keep the task and result, correct
only main-owned metadata in a new safe action, and do not claim completion.

Read attempt diagnostics for failures, rotation, budget tuning, or the usage summary. Give
future workers the approved packet plus compact role reports and raw specialist evidence,
never the entire prior result or hidden dialogue.

## Follow-Ups, Fixes, And Parallel Work

Every runner process is one job and then exits. In runner mode, "same gate" or "same writer"
means the same role, approved route, ownership, and decision responsibility with prior
artifacts supplied explicitly, never a resumed thread.

Each slice of an approved multi-slice plan is a separate job, sequential in one worktree and
linked to the same preflight and revision, with its contract, repository state, and consumed
interfaces. Fast and Standard work stays one job unless preflight upgrades the profile.

Run independent read-only reviews concurrently through separate tool calls when the tool
layer supports it, otherwise sequentially. Outside the Claude Code adapter's background calls,
add no background process; never add a batch command, daemon, shell `&`, or shared scheduler. Keep one active implementation job per worktree. The runner's worktree lock
coordinates cooperating writers, but the workflow still sequences ownership and must not treat
lock failure as a scheduler.

## Reconcile And Finish The Run

Before any final response in runner mode, run `agent-run-manifest reconcile` again. Do not
finish while a job is `pending` or `running`. Once the terminal state is established, close the
run with one of:

```bash
agent-run-manifest finish /absolute/path/to/run.yaml completed
agent-run-manifest finish /absolute/path/to/run.yaml blocked
agent-run-manifest finish /absolute/path/to/run.yaml needs_user_input
agent-run-manifest finish /absolute/path/to/run.yaml stopped
```

`finish` reconciles first, refuses an active job, and refuses any `jobs/*/task.yaml` not
registered through the manifest. Use `completed` only after postflight approval and required
lifecycle actions. If a later user response resumes a terminal run, call
`agent-run-manifest resume /absolute/path/to/run.yaml` before the next job. The helper does not
decide whether a failed historical job was resolved; main and the gates do.
