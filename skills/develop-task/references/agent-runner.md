# Agent Runner Backend

Read this completely when the backend is `runner`, and before the first job off the
home vendor (the Vendor section of the skill). Without the runner backend, read Resolve The Command,
Dispatch A Job (its `--no-manifest` form), Claude And Codex Engines, and Wait And Interpret,
and skip every other `agent-run-manifest` step.

## Resolve The Command

Resolve one `agent-runner` once per run, in this order: an exact path the user
supplied, the nonempty `CODEX_AGENT_RUNNER` variable,
`${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-runner`, then `PATH`. Take
`agent-run-manifest` from the same directory, then from `PATH`. Require both `--help` to
succeed before preflight. Do not install, upgrade, or repair them from inside the
workflow. If either is missing, fail closed and report it; only an explicit user
instruction selects direct subagents.

## Initialize The Run And Model Policy

Once the target worktree is known, before the first job:

```bash
agent-run-manifest init --workspace /absolute/worktree/path
```

Check its exit status before using the output: on failure it prints nothing, and a
later `sed` or `cat` on the empty path waits on stdin forever. On success it prints the
absolute `run.yaml` path in a new private temporary directory; keep it for every later
call.

`init` reads the latest unquoted develop-task invocation from real user messages, in
the rollouts for `CODEX_THREAD_ID` or the Claude transcript for
`CLAUDE_CODE_SESSION_ID`; never delete or move those files. It resolves `D` (an alias for
the single matrix; `A` is rejected), `M` (the model of the invocation turn), and `E
<model>`; without them the policy is `adaptive`. For a plain-language limit, pass your
reading as `--mode main_ceiling` or `--mode explicit_ceiling --maximum-model Luna`; these
cannot contradict explicit parameters, and never pass an invented or default policy over
a recognized one. Report the resulting policy before the first job. A missing source,
ambiguous invocation, unsupported ceiling, or conflict fails before the run exists:
recover the evidence, not an unconstrained substitute.

The helper owns `run.yaml`; never write it, add job entries, or create job directories by
hand. Its fields are in [`run-manifest-schema.md`](run-manifest-schema.md), read only when
you need one. Workers never receive orchestration paths. The matrix, policy, and source
are fixed for the run; do not copy a manifest to another chat to bypass them.

## Dispatch A Job

Write the job packet to a file outside the worktree, then run one foreground command per
job:

```bash
agent-run-manifest dispatch /absolute/run.yaml --role implementation-worker \
  --profile standard --contract-revision 1 --approved-by-preflight 001-preflight \
  --prompt-file /absolute/packet.md
```

It routes the model and effort from the matrix, picks the vendor and its peer
model, applies the run's ceiling, builds the task from the canonical role file
`${CODEX_HOME:-$HOME/.codex}/agents/<role>.toml` with the runner output envelope, sets
permissions and context budgets for the role and profile, registers the job, runs it,
reconciles the manifest, and prints the job, route, model, status, summary, result path,
and the full role report. When a safety refusal stops a routed Fable job, it reruns the
job on Opus xhigh and prints the rerun, with the refused job under `refused`. `agent-run-manifest route` takes the role, profile, and routing
flags (and `--ceiling`) and prints the route without running anything.

- `--role`: `preflight-review`, `implementation-worker`, `postflight-review`,
  `repo-practice-review`, `best-practice-review`, `test-review`, `code-simplicity-review`,
  or `diagnosis-review`. Composed discovery uses these roles too, with no approving
  preflight; a final review-task audit goes in a `postflight-review` packet.
- `--profile`: the confirmed Execution Profile. Specialists use the requesting gate's. For
  `diagnosis-review`, it is the profile of the unresolved cause, not of the task.
- `--slice visual|prose|critical-combined|exceptional`: the slice type preflight named.
- `--for postflight` or `--for diagnosis`: a specialist that gate requested, and the
  Reduction Pass (`code-simplicity-review --for postflight`). Under `--vendor cross` these go
  to the other vendor.
- `--lookup [low|medium|high]`: a specialist's bounded factual lookup on Luna; high to
  correlate several sources, low to pick a check or classify a log.
- `--vendor auto|cross|codex|claude`: the run's vendor choice; pass it to every job. `auto`
  (default) keeps every job on the home vendor, `cross` sends postflight, diagnosis, and
  their specialists to the other vendor, and a vendor name sends every job there. The
  usage-limit fallback reruns a job with `auto`.
- `--model` and `--effort` with `--reason`: a promotion or another route preflight required;
  the ceiling still applies.
- `--contract-revision` is required; `--approved-by-preflight` is required for
  `implementation-worker` and `postflight-review`, and names the approving preflight for
  every other job when one exists. Increment the revision before each fresh preflight for a
  `substantive` or `replan` fix; `mechanical` and `reduction` fixes stay on it.
- `--runner <path>`: an exact runner path the user supplied.
- `--unrestricted`: full access and network for a writer, only when the user explicitly
  allowed unrestricted execution. Never broaden a job because it needs network or an
  approval; ask the user instead.

The packet holds what the role needs: requirements revision, IDs, exact excerpts, sources,
and amendments apart from the hypothesis, the contract revision, and for the writer the
Implementation Contract. Final postflight gets the complete requirement set. Every retry,
gate challenge, specialist interpretation, fix, and postflight cycle is a new dispatch; a
runner process never resumes a conversation, so "the same gate" means the same role, route,
and responsibility with the prior reports in the packet. Exceptional raises the reasoning
tier, not the job size: keep an Astra job bounded. A changed profile or a materially larger
packet needs a new preflight decision.

Without the runner backend, use `dispatch --no-manifest --workspace /absolute/worktree
[--ceiling <model>]` with the same role and routing flags. It writes a private task, runs it,
and prints the same summary, with no manifest.

## Claude And Codex Engines

A `claude-*` model runs through the runner's Claude Code engine, every other model through
Codex, with the same schemas, permissions, worktree lock, and results. The Claude engine
needs a signed-in `claude` on `PATH` or `AGENT_RUNNER_CLAUDE_BIN`. Its Bash runs in Claude's
sandbox, which blocks writes and network for read-only jobs and fails the job when it cannot
start (for example on Linux without bubblewrap). A Claude writer may use Unix sockets and
`/tmp`, so Karma and JVM tests with Mockito run, but it cannot reach Docker, its own run
directory, or the network, including services on the machine's own ports. The sandbox denies
shell expansions such as `$?` and `VAR=value` prefixes, so the runner tells Claude jobs to run
plain commands and gives a writer a scratch directory for scripts. A Claude job has one attempt
and no context rotation. Run `agent-runner`
outside the Codex sandbox: both engines need network access.

## Wait And Interpret

Dispatch runs in the foreground and prints only when the job ends; silence is expected.
Apply the Silent Long-Poll Discipline. When the host exposes the `functions.exec` wrapper,
start the command with this first line:

```javascript
// @exec: {"yield_time_ms": 300000}
```

If the transport yields, stay on the same handle with the longest accepted wait:
`write_stdin` with empty `chars` for a `session_id`, or `functions.wait` for a `cell_id`. Do
not read partial results, repository state, or runner files during the wait.

A nonzero `runner_exit` means no reliable result: stop and report stderr. A
`reconcile_error` or `result_error` is an orchestration error: keep the task and result, fix
only main-owned metadata in a new safe action, and do not claim completion. Otherwise read
`execution_status`:

- `completed`: interpret the role report. It is never approval or success by itself;
- `blocked`: the role could not execute or the writer returned `replan_required` or
  `blocked`; read the report and stop or replan;
- `failed`, `interrupted`, `context_exhausted`: keep the artifacts and decide whether the
  evidence permits a new job;
- `worktree_locked`: never bypass the lock; wait for the known owner or stop;
- `invalid_task`: fix the packet or flags and dispatch again;
- `needs_approval`: stop for user input.

The `.events.jsonl` file next to the result is the job's own log, for diagnosing why it
stopped. It may contain file contents; do not copy it into reports. Give later jobs compact
reports and raw specialist evidence, never a whole prior result. Run independent read-only
reviews as separate parallel calls when the tool layer allows, otherwise in sequence; never
use shell `&`, a daemon, or a scheduler, and keep one implementation job per worktree.

## Record Approved Requirement Changes

Recover an actual explicit developer decision first; a gate conclusion, existing code, or a
stale-ticket claim is not enough. Stop any affected writer, resume a terminal run, then:

```bash
agent-run-manifest amend-requirement /absolute/run.yaml R1 \
  --before 'Temporary report files are allowed with cleanup.' \
  --after 'Generate reports only in memory.' \
  --source 'Developer message <reference>: "Generate reports only in memory."' \
  --reason 'The developer requested no temporary report files.'
```

Use the exact wording, the real message reference, and the reason, or say none was given.
One amendment advances one revision. Keep history intact; later packets carry the original
excerpts and confirmed amendments, and say when the ticket still differs.

## Usage And Finish

`agent-run-manifest usage /absolute/run.yaml` prints the Agent Usage table: every job with
model and effort, status, attempts, uncached, cached, cache-write, and output tokens, totals
that say when they are partial, and a main row from this session. Put it in handoffs and the
final report as printed, with the fix/review cycle count.

Before any final response, reconcile with `agent-run-manifest reconcile`. Once the terminal
state is clear and no job is `pending` or `running`, close the run with
`agent-run-manifest finish /absolute/run.yaml completed` (or `blocked`, `needs_user_input`,
`stopped`). Use `completed` only after postflight approval and the required lifecycle
actions. To continue a terminal run after a user reply, call `agent-run-manifest resume`
first. The helper does not decide whether a failed job was resolved; main and the gates do.
