---
name: develop-task
description: Explicitly invoked engineering workflow for repository implementation tasks with mandatory preflight/postflight review gates, adaptive gpt-5.6-terra/gpt-5.6-sol routing, runner-supervised fresh-context delegation by default, an explicit direct-subagent fallback, focused validation, and standalone lifecycle handling. Use only when the user explicitly writes `$develop-task` or explicitly asks to run the develop-task workflow; otherwise do not select this skill.
---

# Develop Task

## Writing quality

Before drafting user-facing prose for this workflow, read
[`../unslop/SKILL.md`](../unslop/SKILL.md) and apply its relevant editing
guidance. Preserve user-provided wording, exact quotes, and required report
formats when they conflict with that guidance.

## Core Contract

Implement one coherent repository task at a time. Own task framing, model and
agent routing, integration, validation evidence, review coordination, and final
lifecycle actions. Do not invent business requirements.

For every implementation task, including a Fast change:

1. Obtain `preflight-review` approval before the first implementation edit.
   That approval covers one exact implementation-contract revision. Obtain a
   fresh preflight before every later fix cycle that postflight classifies as
   `substantive` or `replan`; only a `mechanical` correction may reuse the
   current revision without another preflight.
2. Run `postflight-review` on the resulting diff before accepting, committing,
   pushing, or submitting the work.

If either mandatory gate is unavailable, fail closed: stop and report the
unavailable component. A run without both gates is not an approved
`develop-task` implementation.

If the request is analysis-only, do not edit files, run mutating commands,
dispatch review roles, or begin this implementation workflow. Answer with
analysis and ask for explicit implementation approval.

Default limits:

- three unresolved postflight cycles;
- five evidence-based challenge iterations per disputed gate decision.

Stop for a user decision when a bounded loop does not converge.

## Delegation Backend

Select one delegation backend at the start of the run and report it in the
first progress update:

- use `runner` by default;
- use `subagents` only when the user explicitly says not to use the runner or
  explicitly asks to use subagents, including phrases such as "не используй
  runner", "не используй ранер", or "используй сабагентов";
- let a later explicit user instruction change the backend only after every
  active delegated job stops; record the switch and preserve completed
  evidence.

Do not infer the fallback from runner unavailability, a failed job, task
difficulty, or convenience. Fail the runner path closed unless the user chooses
the fallback.

For `runner`, read `references/agent-runner.md` completely before the first
preflight job. Dispatch every preflight gate, implementation worker,
postflight gate, and requested specialist through one foreground
`agent-runner` process and YAML artifacts. Do not use collaboration subagent
tools for those roles. The main thread remains the semantic orchestrator and
never delegates orchestration itself.

For `subagents`, preserve the direct custom-agent workflow: spawn roles with
explicit model/effort, `fork_turns: "none"` or bounded history, and compact
self-contained packets; use follow-up turns for the same live gate or writer
when applicable. Do not create runner artifacts or invoke `agent-runner`.

All later instructions to "dispatch", "run", "return to", or "ask" a role use
the selected backend. Core gate semantics, evidence requirements, review
independence, bounded loops, and lifecycle rules are identical across both
backends.

## Ownership Invariants

- Let the main agent own orchestration, gate challenges, integration, and
  lifecycle actions.
- In runner mode, route every implementation, including Fast, through an
  `implementation-worker` runner job.
- For an approved multi-slice Deep or Deep + Critical plan, route each slice
  through a separate fresh `implementation-worker` job and keep the jobs
  sequential in one worktree.
- In direct-subagent mode, let the main agent write product code only for a
  confirmed Fast profile; otherwise use `implementation-worker`.
- Use the generic `implementation-worker` role for every delegated
  implementation; do not add language-specific workers without a demonstrated
  responsibility or tool-surface boundary.
- Allow at most one authorized worktree mutator at a time. A replacement worker
  is allowed only after the current writer stops and ownership is transferred.
- Keep explorers, review gates, and generalist specialists read-only.
- Stop the current writer before transferring ownership to another writer.
- Do not let `implementation-worker` commit, push, open a PR, update external
  systems, or resolve review threads.

## Repository Context

Read applicable `AGENTS.md` files and inspect
`git status --short --untracked-files=all` before routing the task. Stop before
carrying unrelated or overlapping user changes into the implementation when
task isolation is unsafe.

If the repository root contains `front/projects/bakery` plus either
`front/projects/chat` or `back/projects/bakery`, read
`references/ui-bakery.md` before preflight. Otherwise do not load that
reference. Pass only relevant repository guidance into child-agent packets.

## Execution Profiles

Build a preliminary profile after minimal repository inspection. Treat Deep as
Critical when the task combines costly, difficult-to-reverse, or
difficult-to-validate risks.

| Profile | Use when | Preflight | Implementation | Postflight |
| --- | --- | --- | --- | --- |
| Fast | Clear local behavior, established pattern, low blast radius, narrow validation | `gpt-5.6-terra` medium | Runner worker by default; main or direct worker fallback on `gpt-5.6-terra` medium | `gpt-5.6-terra` medium |
| Standard | Clear requirements with non-trivial but bounded implementation | `gpt-5.6-terra` high | Worker on `gpt-5.6-terra` medium by default | `gpt-5.6-terra` high |
| Deep | Cross-layer, novel, ambiguous, high-risk, or difficult to validate | `gpt-5.6-sol` high by default | Worker on `gpt-5.6-sol` high by default | `gpt-5.6-sol` high by default |
| Deep + Critical | Multiple critical risks, costly failure, low reversibility, or failed lower-tier reasoning | `gpt-5.6-sol` xhigh by default | Worker on `gpt-5.6-sol` xhigh by default | `gpt-5.6-sol` xhigh by default |

Critical indicators include security, authentication, permissions, billing,
persistence, migrations, destructive behavior, concurrency, public contracts,
and low-validatability changes.

## Implementation Slicing

Use one implementation job by default for Fast and Standard work. Do not split
a small coherent change merely to create more agents.

Before preflight, identify whether a preliminary Deep or Deep + Critical task
contains multiple independently bounded layers or responsibilities. When one
worker packet would combine several such surfaces, propose ordered
implementation slices. Typical boundaries are a migration or persistence
contract, backend enforcement, API or token contracts, frontend behavior, and
integration coverage. Slice by responsibility and dependency, not by arbitrary
file count.

Require preflight to approve either one implementation job or an exact ordered
slice plan. Every slice must state its responsibility and owned paths, inputs
from earlier slices, acceptance evidence, focused validation, and replan
triggers. All approved slices remain under the same contract revision and are
implemented by separate fresh runner jobs. Keep one worktree writer active at
a time, inspect each result and diff before starting the next slice, and run
postflight on the combined implementation after all slices finish. A slice
that invalidates the approved boundary, ordering, behavior, or critical
contract stops the sequence and returns to fresh preflight.

For Standard implementation, raise `gpt-5.6-terra` from medium to high only
when preflight names concrete reasoning uncertainty, unfamiliar repository
patterns, or difficult validation. For Deep, raise `gpt-5.6-sol` from high to
xhigh for novel architecture, multiple coupled layers, or substantial
uncertainty.

Use `gpt-5.6-sol` max when several critical indicators combine, depth matters more than
speed or usage, failure is especially costly, or a lower Sol tier has already
made a conceptual mistake. Do not use max automatically for every change in a
critical domain.

Every preflight result must name one exact implementation model/effort and one
exact postflight floor, never a range. Use `gpt-5.6-terra` medium by default for
read-heavy specialists in Fast/Standard work, the requesting gate's exact tier
for questions that determine its decision, and the Deep/Critical tier for
questions carrying that risk.

Always pass an explicit model and reasoning effort for every delegated job. Do
not rely on inherited defaults. Runner tasks record both values in YAML and
start fresh ephemeral workers. Direct-subagent spawns must use
`fork_turns: "none"` or a positive bounded history. Every backend receives a
compact self-contained packet even when the selected model matches the parent.

If an approved model or agent role is unavailable, do not silently downgrade or
substitute a weaker route. Use an available equivalent-or-stronger approved
route, repeating preflight if the profile changes materially, or stop with the
unavailable component and required decision.

## Roles

### Main Orchestrator

Do:

- identify the task boundary, acceptance criteria, likely owner, and initial
  technical hypothesis;
- build the preliminary Execution Profile;
- choose the model and reasoning effort for each delegated job;
- select and enforce one delegation backend;
- propose and sequence bounded implementation slices when a Deep or Critical
  task spans multiple separable responsibilities;
- sequence every write-capable agent;
- provide self-contained review and implementation packets;
- inspect actual status, diff, and validation evidence rather than trusting
  summaries;
- challenge gate decisions only with concrete evidence;
- own commits, push, PR, and final reporting when standalone.

Do not:

- silently override a core-gate decision;
- interpret specialist output as the final gate decision;
- edit concurrently with an active implementation worker;
- keep a task on a cheap tier after evidence requires promotion.

### Core Gates

Dispatch `preflight-review` before implementation under each approved contract
revision. Revision 1 covers the initial implementation. Create and approve a
new revision before a postflight-directed fix classified as `substantive` or
`replan`. Dispatch `postflight-review` after every resulting implementation
diff. Let the gates own review decisions and resolve specialist conflicts.

Require postflight to classify the next implementation-affecting mutation:

- `none`: no implementation mutation is required;
- `mechanical`: one obvious local correction with no new technical decision,
  coordinated multi-part edit, behavior or contract change, validation change,
  or profile change; it may reuse the current contract revision;
- `substantive`: a non-trivial fix that adds or changes a technical decision,
  requires coordinated edits, or materially changes validation while remaining
  inside the overall task boundary; it requires a new contract revision and
  fresh preflight;
- `replan`: owner, scope, expected behavior, contracts, critical risks,
  validation obligations, or Execution Profile changed; it requires a new
  contract revision and fresh preflight.

Treat anything beyond a single deterministic local correction as
`substantive`, and choose `substantive` when uncertain. The main orchestrator
may require a fresh preflight after a `mechanical` classification when evidence
warrants more review, but it must never waive `Preflight Required: yes`.
Require `Preflight Required: yes` exactly for `substantive` and `replan`, and
`no` for `none` and `mechanical`. `Approval: yes` requires `Next Change Class:
none`. Treat a missing or inconsistent classification as an incomplete gate
response and return it to the same postflight responsibility for correction.

Require preflight to confirm or upgrade:

- lane and critical flags;
- writer;
- implementation model/effort;
- postflight minimum model/effort;
- replan triggers.

Implementation may start only when preflight returns both `Decision: proceed`
and `Routing status: confirmed`, with no unresolved Blocking specialist
request. `upgrade required` implies `Decision: revise first`; rerun preflight at
the upgraded tier before editing.

### Implementation Worker

Use the single generic `implementation-worker` role for every runner-mode task,
for Standard and Deep direct-subagent tasks, and for a Fast direct-subagent
task when handoff adds useful separation. A multi-slice plan uses the same role
in separate fresh jobs; it does not give the complete cross-layer task to one
logical worker. Assign exact paths or responsibility and remind it that other
user or agent changes may exist.

Return a first `mechanical` postflight fix to the same writer responsibility and
tier. Before any `substantive` or `replan` fix, obtain fresh preflight approval
for the proposed fix contract and its exact route. Runner mode creates a fresh
implementation job with the prior result, diff, validation, findings, contract
revision, and approving preflight job; direct-subagent mode follows up with the
same live writer only after any required fresh gate. Use a new stronger route
only after stopping the current writer and explicitly transferring ownership.

### Generalist Specialists

Let a core gate request these agents only for a concrete question:

- `repo-practice-review` for repository evidence and local precedent;
- `best-practice-review` for general engineering practice;
- `test-review` for focused validation and test quality;
- `code-simplicity-review` for scope, reuse, and unnecessary complexity;

Do not add language-specific implementation workers. Reconsider specialization
only after repeated real tasks demonstrate a distinct responsibility or tool
surface.

### Diagnosis Reviewer

Use `diagnosis-review` only after an attempted fix leaves the same observable
failure unresolved or repeated evidence makes the current causal hypothesis
unreliable. It is a read-only root-cause role, not another implementation
worker. Give it the exact reproduction, failure output, relevant current diff,
prior attempted fix, and any runtime evidence already gathered by the main
thread. Dispatch it through the selected backend and require evidence that
distinguishes confirmed, probable, and unknown causes before another edit.

## Workflow

1. Confirm one current task. If the user provides a list, work only on the
   current coherent item.
2. Stop for requirements discovery when expected product behavior or acceptance
   criteria are too unclear to implement without invention.
3. Read repository instructions, inspect the dirty tree and current branch,
   gather minimal ownership, nearby-pattern, reproduction, and validation
   context, and conditionally load repository-specific guidance.
4. Build the preliminary Execution Profile and, only for a multi-surface Deep
   or Deep + Critical task, a proposed ordered implementation slice plan.
5. Dispatch mandatory `preflight-review` with the user request, preliminary
   profile, current preflight model/effort, task boundary, dirty-tree notes,
   likely files, constraints, expected behavior, selected backend and its writer
   invariant, proposed slices or an explicit single-job choice, and initial
   technical hypothesis.
6. If preflight requests specialists, dispatch only the requested read-only
   roles with explicit model/effort and return their raw reports to the same
   gate responsibility for its updated decision.
7. If preflight requires a stronger tier, rerun preflight before editing. If it
   returns `revise first` or `blocked`, resolve that state before continuing.
8. Build the approved implementation contract or ordered slice contracts
   defined below.
9. In runner mode, dispatch one `implementation-worker` per approved slice,
    sequentially, with the approved model/effort. A normal Fast or Standard
    task has one slice. In direct-subagent mode, let main write only when
    preflight confirms Fast and main already holds the required context inside
    one local ownership boundary; otherwise dispatch the approved writer jobs
    sequentially.
10. After each slice, handle `implemented`, `replan_required`, or `blocked`,
    inspect the actual diff and focused validation, and pass only approved
    prior-slice contracts and compact results to the next fresh writer. Do not
    start the next slice or materially expand the task after a replan trigger.
11. Inspect actual repository status and diff. Run or verify focused validation
    and record failed, unavailable, and skipped checks. The worker should run
    potentially write-producing checks before returning. The main may run a
    worktree-preserving check after the worker stops; transfer authorized-mutator
    ownership explicitly before any check that may update snapshots, generated
    files, lockfiles, caches inside the repository, or other artifacts, then
    inspect the resulting diff.
12. Recalculate the effective postflight floor from the original request,
    preflight profile, actual diff, worker deviations, and validation gaps.
13. Dispatch mandatory independent `postflight-review` with the task packet,
    preflight decision, writer result, changed files, diff, validation, current
    cycle, contract revision, approving preflight, and prior findings/fixes.
14. If postflight requests specialists, return their raw results to the same
    gate for its final classification. Approval is impossible while a Blocking
    specialist request remains unresolved.
15. Relay postflight findings in the main chat before any writer resumes.
16. Follow postflight's next-change classification. Return a `mechanical` fix
    to the same writer under the current revision. For a `substantive` or
    `replan` fix, define the proposed next contract revision and dispatch a
    fresh preflight before any writer resumes. Rerun affected validation and
    repeat postflight after every mutation.
17. If an attempted fix leaves the same observable failure unresolved, stop
    code edits and follow Repeated Failure Diagnosis below before another
    implementation job. Otherwise promote or replan after a repeated
    conceptual failure, low confidence, or unexpected scope/risk growth.
18. After approval, create logical commits and a draft PR for standalone work
    unless the user asked to keep changes local. In embedded mode, defer
    lifecycle actions to the outer workflow.
19. Report the final state.

## Implementation Contract

Provide the writer a compact self-contained packet:

```text
Goal:
Acceptance criteria:
Owned paths/responsibility:
Out of scope:
Relevant repository evidence:
Contracts to preserve:
Implementation hypothesis:
Dirty-tree constraints:
Validation commands/expectations:
Replan triggers:
Expected return:
```

Keep goal, acceptance criteria, ownership, out-of-scope boundary, preserved
contracts, validation expectations, and replan triggers strict. Keep the
implementation hypothesis flexible. Allow the writer to adjust local code
shape, naming, helper usage, and test structure within the approved contract.

Require this response:

```text
Status:
- implemented | replan_required | blocked

Changes:
Decisions:
Validation:
Deviations from hypothesis:
Replan reason:
Remaining risks:
```

Treat these as replan triggers:

Any implementation need that is beyond or different from the approved task
packet, including:

- changing user-visible behavior or acceptance criteria beyond the approved goal;
- moving to an owner, subsystem, or layer outside approved responsibility;
- adding an unapproved dependency or architecture;
- changing schema, migration, public API, auth, permissions, billing,
  security, persistence, concurrency, or another critical contract not named in
  the approved packet;
- materially expanding files or responsibility beyond approved ownership;
- removing, weakening, or intentionally skipping approved validation;
- making an unsupported product assumption.

Inability to run an approved validation command because tooling or access is
unavailable is `blocked`, not `replan_required`.

## Repeated Failure Diagnosis

When one attempted fix leaves the same observable test, runtime, UI, or CI
failure unresolved, do not make another speculative code or test edit. Stop the
writer, preserve the exact reproduction and output, and dispatch a fresh
read-only `diagnosis-review` through the selected backend. The diagnosis packet
must include the failed hypothesis and edit, current diff, commands and logs,
and concrete DOM, state, request, or runtime observations when relevant.

Require the diagnosis to label its cause `confirmed`, `probable`, or `unknown`
and cite evidence that distinguishes it from rejected hypotheses. Gather
authorized runtime evidence directly before the review when a read-only runner
cannot access the required browser, network, or write-producing test surface;
the diagnosis reviewer still interprets that evidence and does not edit. Do not
start another implementation job on an `unknown` cause merely to try a new
guess. A confirmed or sufficiently evidenced probable cause becomes a proposed
fresh contract revision and returns to preflight before another mutation.

Do not invoke this gate for a clearly different failure, a proven transient
infrastructure error, or a first failure whose cause is already directly
established by evidence.

When a worker returns `replan_required`, preserve its evidence and current diff,
stop further expansion, and return to preflight if owner, boundary, behavior,
risk tier, or contracts changed. Update only the task packet for a local
technical adjustment that stays inside the approved contract.

## Promotion Policy

- First local blocking finding: preserve the same writer responsibility when
  appropriate, but follow postflight's next-change classification. A
  `mechanical` correction may reuse the current revision and tier; a
  `substantive` correction requires fresh preflight before a new writer job;
  `replan` requires fresh preflight over the changed boundary or profile.
- Repeated conceptual finding, low confidence, or unexpected risk/scope growth:
  stop the current writer, return to preflight when the approved profile is
  invalid, promote the model/effort, and give the new writer a fresh packet with
  current diff and findings.
- A different small finding in a later cycle does not automatically require
  promotion.
- Stop after three unresolved postflight cycles and ask the user for a decision.

## Delegation Rules

Let core gates decide which specialist to use, the exact question, required
artifacts, and whether the result is blocking or advisory. Do not let gates
delegate recursively. Let the main agent select the concrete model/effort from
the Execution Profile and technically dispatch every specialist on behalf of
the requesting gate through the selected backend.

Do not expand, narrow, rewrite, or independently adjudicate a specialist
request. Return its raw report to a fresh runner gate job with the complete
prior gate report in runner mode, or to the same live gate in direct-subagent
mode. Act only on the gate's updated decision.

In runner mode, use separate immutable job directories for every gate follow-up,
specialist, implementation fix, and postflight cycle. A completed runner
process has no resumable conversation; continuity comes only from task packets,
result artifacts, repository state, and explicit handoffs. In direct-subagent
mode, use the existing agent mailbox and follow-up mechanisms.

When specialist outputs conflict, require the gate to decide explicitly whether
to follow repository practice, depart from it, take a transitional local fix,
or stop for user input.

## Silent Long-Poll Discipline

Use the same quiet wait behavior for every live foreground process and every
post-PR lifecycle wait in the current turn. This includes runner jobs, tests,
builds, CI, preview or deployment readiness, E2E, and review or check refreshes.
Keep this discipline when an outer workflow owns those lifecycle actions; it
does not transfer lifecycle ownership to `develop-task`.

- Prefer one existing foreground watch command or blocking tool call. Do not
  add a custom CI monitor, daemon, background service, or polling script solely
  to keep the model idle.
- When the tool yields a live session, cell, process, or wait handle, continue
  on that same handle with `yield_time_ms: 300000`, or the largest supported
  value when five minutes is unavailable.
- If the wait returns early with the same live state and no semantic change,
  repeat it silently. Do not send elapsed-time reminders or "still waiting"
  commentary.
- Report only a semantic stage change, terminal success, failure, approval or
  user-decision request, or a transport problem that changes the next action.
- Do not inspect process state, logs, repository files, CI status, or
  heartbeats merely to prove that unchanged work is alive.

If no blocking watcher exists and status must be queried again, wait five
minutes before the next query and keep unchanged results silent. A user status
request permits one current snapshot, then the same quiet wait resumes.

## Embedded And Lifecycle Policy

When another explicitly invoked workflow wraps `develop-task`, treat it as the
outer lifecycle controller unless the user says otherwise. Keep engineering
gates, model routing, implementation ownership, validation evidence, and
approval state inside `develop-task`. Do not independently commit, push, edit a
PR, update external trackers, wait on CI, or resolve review threads unless the
outer workflow delegates that exact action.

For approved standalone repository work, normally finish with a branch when
needed, logical commits, push, and a draft PR. Do not create a PR for
analysis-only, no-op, blocked, unsafe dirty-tree, or unapproved work, or when the
user asks to keep changes local.

Before committing:

- ensure implementation is complete;
- run focused validation or document skipped checks;
- obtain postflight approval; an explicit request to proceed after
  `Approval: no` terminates this workflow as unapproved and must not trigger
  commit, push, or PR actions inside `develop-task`;
- ensure task changes can be isolated safely.

Any implementation-affecting mutation after postflight approval, including a
rebase resolution, generated-file update, formatter rewrite, or test-produced
tracked artifact, invalidates that approval. Inspect
the new diff, rerun affected validation, and obtain fresh postflight approval
before lifecycle actions continue. If that post-approval mutation is more than
a single deterministic local correction, create a new contract revision and
obtain fresh preflight approval before editing; this includes voluntarily
accepting a Recommended or Optional implementation change after approval.

## Terminal-State Gate

Treat the final response as completion of the current turn. Never use it as a
progress update or promise of future in-scope work.

Before sending a final response, verify all of the following:

- no delegated job, command, validation, CI watch, or required wait remains
  active;
- no next in-scope action can be taken without new user input or external state;
- a successful implementation has current postflight approval and no later
  implementation-affecting mutation;
- runner mode has a reconciled `run.yaml` with no `pending` or `running` job and
  a terminal run status, unless reconciliation/finalization itself is the exact
  blocker being reported;
- the final response names one honest workflow state: `completed`, genuinely
  `blocked`, `needs_user_input`, or explicitly `stopped_by_user`.

If the response would say "work continues", "I will retry", "I will fix next",
"still running", or equivalent future-work language, do that work or continue
the foreground wait instead of sending the final response. `invalid_task`, a
failed validation, a rejected hypothesis, or an unapproved postflight is not a
blocker while a safe next action remains. An explicit user instruction to
ignore a wall-clock or skill timebox makes elapsed time invalid as a blocker;
continue until another terminal condition above is real.

A required approval, missing product decision, exhausted bounded review loop,
unavailable mandatory component, unsafe dirty-tree conflict, or external state
the workflow cannot change may be a genuine blocker. State the exact condition
and required next decision rather than implying that work is continuing.

## Postflight Relay

After every postflight response, report in the main chat:

- Blocking findings, or `none`;
- Recommended findings accepted or declined with a reason, or `none`;
- notable Optional findings, or `none`;
- Validation gaps, or `none`;
- Failure class and routing recommendation;
- Next Change Class, whether fresh preflight is required, and why;
- current contract revision and approving preflight job;
- Approval and review cycle.

## Report Format

When done, report:

- Problem and cause, when applicable;
- Execution Profile and writer;
- Fix;
- Validation and skipped checks;
- Preflight and postflight results and cycle count;
- implementation-contract revisions and their approving preflight jobs;
- Replans or promotions, or `none`;
- delegation backend and, for runner mode, the `run.yaml` path;
- PR URL/state, or why no PR was created;
- branch and uncommitted/committed/pushed state;
- whether user approval or another decision remains.

Keep the final response concise and concrete.
