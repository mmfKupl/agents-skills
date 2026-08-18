# Codex agent runner v1

`agent-runner` is a foreground CLI for exactly one immutable YAML task. It starts one private Codex App Server through the stable Python SDK, runs one ephemeral worker at a time, writes one unique YAML result, prints that result's absolute path to stdout, and exits. Launch separate processes for independent batch or parallel work; there is no daemon, queue, scheduler, MCP server, or persistent conversation history.

## Install and run

Requirements: Python 3.10 or newer on POSIX. Advisory locking uses `fcntl`, so Windows is not supported.

```bash
python3.12 -m venv .venv
.venv/bin/pip install ./agent-runner
.venv/bin/agent-runner /absolute/path/to/task.yaml
```

The runtime dependencies are exactly `openai-codex==0.147.0` and `PyYAML==6.0.3`. The SDK installs its pinned `openai-codex-cli-bin==0.147.0` runtime and reuses existing Codex authentication. stdout contains only the absolute result path. Diagnostics go to stderr. Every successfully finalized, trustworthy result exits 0, regardless of its semantic status. Failure to create or finalize a reliable result exits 3. The YAML result—not the process exit code or console text—is the semantic source of truth.

The main agent or caller must place the task and its derived `results/` directory outside the target workspace and repository, normally under a private temporary job directory. The runner always derives results beside the supplied task and intentionally does not enforce that location policy.

## Task contract

Tasks are strict `agent-task` schema v1 YAML. Every shown field is required except `developer_instructions`. Unknown and duplicate keys are rejected. Strings marked nonempty may not contain only whitespace. Numeric limits must be finite; attempts must be a positive integer.

```yaml
kind: agent-task
schema_version: 1
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
    soft_limit_percent: 75
    hard_limit_percent: 90
    checkpoint_grace_seconds: 20
  max_attempts: 3
  timeout_seconds: 1800
```

The runner reads the original bytes once, records their SHA-256, and never rewrites the task. `workspace.cwd` must be an absolute existing directory. v1 always uses explicit deny-all approvals; it never silently approves or enables auto-review.

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

For `/path/to/task.yaml`, every invocation creates a different `/path/to/results/<execution-id>.yaml`. It first writes status `running`, then rewrites the same result atomically using a same-directory temporary file, file `fsync`, `os.replace`, and directory `fsync`. Milestones and usage events are persisted immediately; noisy progress events use a rate-limited heartbeat. Lock files are always external, but avoiding result artifacts in the repository depends on the caller placing the task outside it as required above.

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
  version: 1.0.0
  sdk_version: 0.147.0
  sdk_package: openai-codex
  runtime_package: openai-codex-cli-bin==0.147.0
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

Attempts record fresh thread and turn IDs, timestamps, status, peak observed context percentage, last and total token usage, and a structured checkpoint or fallback partial output when rotation is needed. Top-level usage sums the final per-attempt totals. Terminal statuses are `completed`, `blocked`, `failed`, `interrupted`, `timed_out`, `worktree_locked`, `invalid_task`, and `context_exhausted`. `needs_approval` is reserved for future schemas and is unreachable under v1 deny-all policy.

## Context rotation, timeout, and cleanup

The runner observes public `thread/tokenUsage/updated` stream events and computes pressure from `last.totalTokens / modelContextWindow`; accumulated thread totals are recorded but do not drive rotation. At the soft percentage it steers once for a structured checkpoint. At the hard percentage, or after checkpoint grace expires, it interrupts and waits for the old turn to become terminal before starting a fresh ephemeral thread. Only the task, fixed instructions, and the structured checkpoint (or fallback partial agent output) cross the boundary; dialogue history does not.

The terminal SDK turn status is authoritative. Structured output can complete or block a run only when the turn itself completed. A failed turn remains failed even if it emitted valid JSON first. A context-interrupted turn can contribute a valid checkpoint only as carry into a fresh attempt.

Thresholds are best-effort at SDK event boundaries. A model may emit a usage event after it has crossed a threshold, and a missing model context window prevents percentage supervision for that attempt. The one monotonic `timeout_seconds` deadline covers SDK startup and all attempts. On timeout, SIGINT, or SIGTERM, the runner requests interruption for an active turn, waits a bounded cleanup interval, closes the SDK/private App Server, and finalizes the result when possible. SIGKILL, power loss, or host failure can leave a valid `running` result because no process can perform cleanup afterward.

## Concurrency and locking

Read-only runs take no lock and can overlap. `workspace_write` and `danger_full_access` take a nonblocking POSIX advisory lock keyed by the canonical Git worktree root, falling back to canonical cwd outside Git. Lock files live under the platform temporary directory. A conflict produces `worktree_locked`. The lock only coordinates cooperating agent-runner processes; it does not stop editors, Git commands, or other programs.
