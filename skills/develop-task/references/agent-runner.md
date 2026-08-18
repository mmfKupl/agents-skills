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

The main thread exclusively creates and updates `run.yaml`, job directories,
and every `task.yaml`. The runner exclusively creates result files. Workers
must not receive orchestration paths and must not edit orchestration files.

Use a monotonically increasing sequence plus a short role slug for job
directories. Treat a task file as immutable after its process starts. Create a
new job directory for every retry, gate challenge, specialist result
interpretation, postflight cycle, or writer fix instead of editing an old task.

Maintain this compact main-owned run index:

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
    task_path: <absolute task path>
    result_path: null
    status: running
    model: gpt-5.6-terra
    reasoning_effort: high
```

After each process finishes, record its absolute result path, semantic status,
execution ID, and relevant usage totals. Keep full role reports in their result
files; do not copy them wholesale into `run.yaml`.

## Create One Task

Write exactly one strict `agent-task` v1 document per invocation:

```yaml
kind: agent-task
schema_version: 1
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
    soft_limit_percent: 70
    hard_limit_percent: 88
    checkpoint_grace_seconds: 30
  max_attempts: 3
  timeout_seconds: 2400
```

Every field shown is required except `agent.developer_instructions`, which this
workflow always supplies for delegated roles. Use absolute existing workspace
paths. Preserve exact approved model and effort values.

## Role Contracts And Output Envelope

Supported roles are:

- `preflight-review`;
- `implementation-worker`;
- `postflight-review`;
- `repo-practice-review`;
- `best-practice-review`;
- `test-review`;
- `code-simplicity-review`.

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

Use these v1 combinations only:

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

## Initial Supervision Budgets

Use these conservative v1 defaults until real runs justify a matrix revision:

| Profile | soft | hard | grace seconds | attempts | timeout seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fast | 75 | 90 | 20 | 2 | 1200 |
| Standard | 70 | 88 | 30 | 3 | 2400 |
| Deep | 65 | 85 | 45 | 4 | 3600 |
| Deep + Critical | 60 | 82 | 60 | 5 | 5400 |

Use the requesting gate's effective profile for specialists. A changed profile
or a materially larger task packet requires a new preflight decision before
implementation. Record observed attempts and usage in `run.yaml`; do not claim
that these limits are a precise total-token cap.

## Execute And Interpret

Invoke the resolved command in the foreground with the one task path. The tool
call may remain pending while the private App Server works; do not poll it with
model turns. stdout must contain one absolute result path.

The process exit code reports transport reliability, not semantic success:

- exit `0`: a trustworthy YAML result was finalized; inspect it;
- nonzero: no reliable finalized result is guaranteed; stop the job and report
  stderr plus any safely discoverable running artifact.

Validate the result kind/schema, task path/hash, and terminal execution status
before using the role report. Route statuses as follows:

- `completed`: interpret `outcome.report` according to the role contract;
- `blocked`: interpret the role report and stop or replan as required;
- `failed`, `interrupted`, `timed_out`, or `context_exhausted`: preserve the
  artifact and decide whether evidence permits a new job;
- `worktree_locked`: do not bypass the lock; wait for the known owner to finish
  or stop with the conflict;
- `invalid_task`: correct orchestration-owned YAML in a new job directory;
- `needs_approval`: reserved; treat it as a stop requiring user input.

Read attempt diagnostics only for failure, rotation analysis, or budget tuning.
Pass future workers the approved task packet plus compact role reports and raw
specialist evidence, never the entire prior result or hidden dialogue.

## Follow-Ups, Fixes, And Parallel Work

Every runner process is one job and then exits. A later challenge or fix uses a
fresh invocation. In runner mode, "same gate" or "same writer" means the same
role, approved model/effort, ownership, and decision responsibility with all
relevant prior artifacts supplied explicitly; it never means a resumed hidden
thread.

Run independent read-only reviews concurrently through separate foreground
tool calls when the tool layer supports parallel calls. Otherwise run them
sequentially. Do not add a batch command, background process, daemon, shell
`&`, or shared scheduler.

Keep only one active implementation job per worktree. Different
`agent-runner` processes already coordinate cooperating writers with a
worktree lock, but `develop-task` must still sequence ownership explicitly and
must not treat lock failure as a scheduler.
