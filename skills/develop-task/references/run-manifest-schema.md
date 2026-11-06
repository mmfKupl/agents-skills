# Run manifest schema

The shape of `run.yaml`, for reading it. `agent-run-manifest` writes this file; never edit it
by hand. Read this only when you need a field or are diagnosing a manifest error.

```text
kind: develop-task-run
schema_version: 1
run:
  id: string
  backend: runner
  workspace: absolute path
  status: running | completed | blocked | needs_user_input | stopped
  started_at: UTC timestamp
  finished_at: UTC timestamp | null
  routing_matrix: D (A only in historical runs)
  model_policy:
    mode: adaptive | explicit_ceiling | main_ceiling
    maximum_model: supported GPT or Claude model | null
  model_policy_source:
    thread_id: session the invocation came from
    turn_id: invocation turn or message
    message_sha256: SHA-256 of the invocation message
  requirements:
    revision: integer, starts at 1
    amendments:
      - requirement_id, before, after, source, reason: string
        revision: integer
jobs:
  - id: string, also the job directory name
    role: supported role name
    contract_revision: positive integer
    requirements_revision: recorded revision
    approved_by_preflight: job id | null
    task_path: absolute path
    result_path: absolute path | null until the job ran
    status: pending | running | completed | blocked | needs_approval | failed | interrupted |
            worktree_locked | invalid_task | context_exhausted
    execution_id: string | null
    usage: null | mapping
      input_tokens: integer, includes cached input and cache writes
      cached_input_tokens: integer
      cache_write_input_tokens: integer
      output_tokens: integer
      reasoning_output_tokens: integer, part of output
      total_tokens: integer
    model: the model that runs, same as selected_model
    requested_model: model before the ceiling
    selected_model: model after the ceiling
    limited_by: explicit_ceiling | main_ceiling | null
    reasoning_effort: string
```

`init` starts with `jobs: []`, `new-job` adds an entry with status `pending`, and `reconcile`
fills `result_path`, `status`, `execution_id`, and `usage` from the result file. Full role reports
stay in result files. Older runs may lack `routing_matrix`, `requirements`, `model_policy`, and
the per-job model fields.
