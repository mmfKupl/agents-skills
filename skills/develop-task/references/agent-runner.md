# Agent Runner Backend

Read this reference completely when the selected delegation backend is
`runner`. Do not load it for the explicit `subagents` fallback.

## Resolve The Command

Resolve one executable once per `develop-task` run, in this order:

1. an exact path explicitly supplied by the user;
2. the nonempty `CODEX_AGENT_RUNNER` environment variable;
3. `${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-runner`;
4. `agent-runner` from `PATH`.

Require `agent-runner --help` to succeed before preflight. Do not install,
upgrade, or repair the runner from inside `develop-task`. If no executable is
available, fail closed and report the setup problem. Do not silently switch to
direct subagents; only an explicit user instruction may select that backend.

Resolve the companion `agent-run-manifest` executable from the same directory
as the selected runner, then from `PATH`. Require `agent-run-manifest --help`
to succeed before creating `run.yaml`. It is a one-shot YAML helper, not a
daemon or scheduler.

## Run Directory And Ownership

Create one private temporary run directory outside the repository and target
worktree. Prefer the platform temporary directory and permissions no broader
than `0700`.

```text
<temporary-root>/codex-agent-runs/<run-id>/
├── run.yaml
└── jobs/
    ├── 001-preflight/
    │   ├── task.yaml
    │   └── results/<execution-id>.yaml
    ├── 002-implementation/
    │   ├── task.yaml
    │   └── results/<execution-id>.yaml
    └── 003-postflight/
        ├── task.yaml
        └── results/<execution-id>.yaml
```

The main thread creates `run.yaml`, job directories, every `task.yaml`, and the
semantic job plan. The runner exclusively creates result files. The
`agent-run-manifest` helper exclusively reconciles result-derived job fields
and run lifecycle timestamps under a short file lock with atomic replacement.
Workers must not receive orchestration paths and must not edit orchestration
files.

Use a monotonically increasing sequence plus a short role slug for job
directories. Treat a task file as immutable after its process starts. Create a
new job directory for every retry, gate challenge, specialist result
interpretation, postflight cycle, or writer fix instead of editing an old task.

Maintain this compact run index:

```yaml
kind: develop-task-run
schema_version: 1
run:
  id: <unique-id>
  backend: runner
  workspace: /absolute/worktree/path
  status: running
  started_at: <UTC timestamp>
  finished_at: null
jobs:
  - id: 001-preflight
    role: preflight-review
    contract_revision: 1
    approved_by_preflight: null
    task_path: <absolute task path>
    result_path: <absolute result path>
    status: completed
    execution_id: <runner execution id>
    usage: <result usage mapping>
    model: gpt-5.6-terra
    reasoning_effort: high
  - id: 002-implementation
    role: implementation-worker
    contract_revision: 1
    approved_by_preflight: 001-preflight
    task_path: <absolute task path>
    result_path: null
    status: pending
    execution_id: null
    usage: null
    model: gpt-5.6-terra
    reasoning_effort: medium
```

Create a job entry as `pending` immediately before its foreground runner call.
After each process finishes, run `agent-run-manifest reconcile <run.yaml>`; do
not hand-copy its result path, execution status, ID, or usage. Reconciliation
verifies the immutable task hash and job ID, rejects multiple executions in one
job directory, and writes those derived fields atomically. Keep full role
reports in result files; do not copy them wholesale into `run.yaml`.

Start at `contract_revision: 1` and increment it before every fresh preflight
for a `substantive` or `replan` fix. A `mechanical` fix remains on the current
revision. Preflight jobs use `approved_by_preflight: null`; every implementation
and postflight job must name the exact approving preflight job. Other gate or
specialist follow-ups record the current revision and use the approving
preflight when one already exists. This linkage is required even when the same
role, model, or writer responsibility continues.

## Create One Task

Write exactly one strict `agent-task` v2 document per invocation:

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
  model: gpt-5.6-terra
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

Every field shown is required except `agent.developer_instructions`, which this
workflow always supplies for delegated roles. Use absolute existing workspace
paths. Preserve exact approved model and effort values.

Include the current contract revision and, for implementation and postflight,
the approving preflight job ID inside `job.prompt` as part of the self-contained
packet. These orchestration fields remain in `run.yaml`; do not add unsupported
keys to the strict `agent-task` v2 document.

## Role Contracts And Output Envelope

Supported roles are:

- `preflight-review`;
- `implementation-worker`;
- `postflight-review`;
- `repo-practice-review`;
- `best-practice-review`;
- `test-review`;
- `code-simplicity-review`;
- `diagnosis-review`.

Treat `${CODEX_HOME:-$HOME/.codex}/agents/<role>.toml` as the canonical role
contract. Read its complete `developer_instructions` and place them in the task
developer instructions. If the canonical file is unavailable, fail that
mandatory role closed instead of reconstructing it from memory.

Append these adapter instructions to every role contract:

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

For `implementation-worker`, encode role status `implemented` as universal
`completed`. Encode role status `replan_required` or `blocked` as universal
`blocked`, and preserve the exact role status and explanation in `report`.

The main thread must interpret the role report. Never equate runner
`completed` with preflight approval, postflight approval, or successful
implementation without reading that report.

## Permission Mapping

Use these v2 combinations only:

| Job | sandbox_mode | network_access |
| --- | --- | --- |
| Every review or specialist | `read_only` | `false` |
| Normal implementation | `workspace_write` | `false` |
| Implementation when the root run is explicitly unrestricted | `danger_full_access` | `true` |

Always use `approval_policy: never`. Never broaden a job to full access merely
because it needs network or an approval. If a safe task requires an unsupported
permission combination, stop and ask the user to change the task, explicitly
select direct subagents, or explicitly authorize unrestricted execution.

The runner cannot pause for interactive approval. A denied operation becomes a
semantic result that the main thread must surface. Do not retry it with broader
permissions without a new user decision.

## Supervision Budgets

Use these profile defaults:

| Profile | soft | hard | grace seconds | attempts |
| --- | ---: | ---: | ---: | ---: |
| Fast | 155,000 tokens | 180,000 tokens | 20 | 2 |
| Standard | 155,000 tokens | 180,000 tokens | 30 | 3 |
| Deep | 210,000 tokens | 240,000 tokens | 45 | 4 |
| Deep + Critical | 350,000 tokens | 400,000 tokens | 60 | 5 |

Use the requesting gate's effective profile for specialists. A changed profile
or a materially larger task packet requires a new preflight decision before
implementation. These limits control the latest worker turn's context, not a
job's cumulative token usage or credits. Record observed attempts and usage in
`run.yaml`. Runner jobs have no wall-clock timeout; the foreground caller may
stop one explicitly with SIGINT or SIGTERM.

## Execute, Wait, And Interpret

Invoke the resolved command in the foreground with the one task path. stdout
must contain one absolute result path when the process exits.

Apply the skill's Silent Long-Poll Discipline throughout this wait. The rules
below only map that discipline to the runner's two possible live handles.

When the host exposes the programmatic `functions.exec` wrapper, start the
foreground invocation with this first-line pragma so the outer cell also uses
the five-minute wait window:

```javascript
// @exec: {"yield_time_ms": 300000}
```

The transport may then yield either a nested shell `session_id` or an outer
`functions.exec` `cell_id` before `agent-runner` exits. Treat both as
transport-level yielding, not as job events:

- for a live `session_id`, wait with `write_stdin` using empty `chars` and
  `yield_time_ms: 300000`;
- when `functions.exec` reports `Script running with cell ID ...`, wait with
  `functions.wait` using that `cell_id` and `yield_time_ms: 300000`;
- continue with the same wait primitive and identifier until it returns a
  terminal result; never alternate to short polling merely to check liveness;
- if the host caps a wait below five minutes, use its maximum accepted wait and
  repeat silently.

While either transport remains alive:

- repeat that maximum five-minute long poll without commentary when it returns
  the same live transport and no material state change;
- never use short periodic polls merely to prove that the process is alive;
- do not emit messages such as "still running", "still waiting", elapsed-time
  reminders, or restatements of the unchanged phase;
- do not inspect processes, heartbeats, partial result YAML, repository state,
  or runner-owned files only to manufacture a progress update;
- report only a terminal process/result, transport failure, approval or user
  decision request, or a real semantic stage change that affects the workflow.

If the user explicitly asks for status while the process is running, answer
once from the current session state and then resume the same five-minute
long-poll protocol. The absence of stdout is expected because the runner prints
only its final result path. Waiting must not create model turns whose sole
purpose is narrating unchanged state.

The process exit code reports transport reliability, not semantic success:

- exit `0`: a trustworthy YAML result was finalized; inspect it;
- nonzero: no reliable finalized result is guaranteed; stop the job and report
  stderr plus any safely discoverable running artifact.

Validate the result kind/schema, task path/hash, and terminal execution status
before using the role report. Route statuses as follows:

- `completed`: interpret `outcome.report` according to the role contract;
- `blocked`: interpret the role report and stop or replan as required;
- `failed`, `interrupted`, or `context_exhausted`: preserve the
  artifact and decide whether evidence permits a new job;
- `worktree_locked`: do not bypass the lock; wait for the known owner to finish
  or stop with the conflict;
- `invalid_task`: correct orchestration-owned YAML in a new job directory;
- `needs_approval`: reserved; treat it as a stop requiring user input.

After validating the result, invoke `agent-run-manifest reconcile` and read the
reconciled job entry before creating another job. Treat reconciliation failure
as an orchestration error: preserve the immutable task and result, correct only
main-owned metadata in a new safe action, and do not claim the run completed.

Read attempt diagnostics only for failure, rotation analysis, or budget tuning.
Pass future workers the approved task packet plus compact role reports and raw
specialist evidence, never the entire prior result or hidden dialogue.

## Follow-Ups, Fixes, And Parallel Work

Every runner process is one job and then exits. A later challenge or fix uses a
fresh invocation. In runner mode, "same gate" or "same writer" means the same
role, approved model/effort, ownership, and decision responsibility with all
relevant prior artifacts supplied explicitly; it never means a resumed hidden
thread.

An approved multi-slice Deep or Deep + Critical implementation uses a separate
fresh runner job for every ordered slice. Keep those writer jobs sequential in
one worktree and link each to the same approving preflight and contract
revision. Pass a later slice only its approved contract, repository state, and
compact prior-slice results. Fast and Standard work remains one implementation
job unless preflight upgrades the task profile; do not micro-slice it.

A `mechanical` fix may keep the current `contract_revision`. Before a
`substantive` or `replan` fix, create the next revision, dispatch a fresh
preflight job, and link the later implementation and postflight jobs to that
approval in `run.yaml`.

Run independent read-only reviews concurrently through separate foreground
tool calls when the tool layer supports parallel calls. Otherwise run them
sequentially. Do not add a batch command, background process, daemon, shell
`&`, or shared scheduler.

Keep only one active implementation job per worktree. Different
`agent-runner` processes already coordinate cooperating writers with a
worktree lock, but `develop-task` must still sequence ownership explicitly and
must not treat lock failure as a scheduler.

## Reconcile And Finish The Run

Before any final response in runner mode, run reconciliation again:

```bash
agent-run-manifest reconcile /absolute/path/to/run.yaml
```

Do not finish while any job is `pending` or `running`. Once the semantic
terminal state is established, atomically close the manifest with exactly one
of:

```bash
agent-run-manifest finish /absolute/path/to/run.yaml completed
agent-run-manifest finish /absolute/path/to/run.yaml blocked
agent-run-manifest finish /absolute/path/to/run.yaml needs_user_input
agent-run-manifest finish /absolute/path/to/run.yaml stopped
```

`finish` reconciles first and refuses an active job. Use `completed` only after
postflight approval and required lifecycle actions. If a later user response
legitimately resumes a terminal run, call
`agent-run-manifest resume /absolute/path/to/run.yaml` before adding the next
job. The helper does not decide whether a failed historical job was
semantically resolved; the main thread and gates retain that responsibility.
