---
name: develop-task
description: Engineering workflow for repository implementation with mandatory preflight and postflight gates, model routing, and cross-vendor review. Use only when the user explicitly writes `$develop-task` (or `/develop-task` in Claude Code) or asks to run this workflow.
---

# Develop Task

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`references/claude-code.md`](references/claude-code.md) before
anything else. It maps Codex tools, model names, and delegation to Claude Code;
every gate and rule in this skill still applies.

## Task title

At entry, read [`../chat-title/SKILL.md`](../chat-title/SKILL.md) and follow it with
the type `develop`. `D` requires the requested implementation, validation, and any
applicable outer-workflow completion gates, not merely a finished code edit.

## Tracker ticket title

When the task has a known ticket, read
[`../ticket-title/SKILL.md`](../ticket-title/SKILL.md) once its requirements are
established, in standalone and embedded mode. Analysis-only requests do not rename.

## Core Contract

Implement one coherent repository task at a time. Own task framing, model and
agent routing, integration, validation evidence, review coordination, and final
lifecycle actions. Do not invent business requirements.

Before the first delegated job, resolve the routing matrix and model policy. In
runner mode, create the run through `agent-run-manifest init`; do not hand-write
`run.yaml` or replace an explicit `M`/`E` with the default policy.

For every implementation task, including a Fast change:

1. Obtain `preflight-review` approval before the first implementation edit. It
   covers one exact implementation-contract revision. Obtain a fresh preflight
   before every later fix that postflight classifies as `substantive` or `replan`.
2. Run the Reduction Pass on the resulting diff and apply its cut list.
3. Run `postflight-review` on the reduced diff before accepting, committing,
   pushing, or submitting the work.

If either gate or the reduction reviewer is unavailable, fail closed: stop and
report the component. A run without them is not an approved `develop-task`
implementation.

If the request is analysis-only, do not edit files, run mutating commands, dispatch
review roles, or begin this workflow. Answer with analysis and ask for explicit
implementation approval.

Limits: three unsuccessful final review rounds (Bounded Review Loop) and five
evidence-based challenges per disputed gate decision. Stop for a user decision when
a bounded loop does not converge.

## Explicit workflow composition

When the user explicitly invokes `$brainstorm-task` and/or `$review-task` alongside
`$develop-task` for the same task, read
[`references/composed-workflows.md`](references/composed-workflows.md) before the
first delegated job. Add only the requested phase. Quoted examples, references, or
analysis-only requests do not select it. Main coordinates all phases with one
backend, matrix, ceiling, and runner run; keep any separately authorized outer
lifecycle controller, and never weaken mandatory gates.

## Requirements Fidelity

The source of truth is the original task specification plus later explicit decisions
by the requesting developer. Repository precedent, simplicity, existing code, a
main-agent hypothesis, and preflight approval cannot remove, narrow, or replace a
requirement. Simplify its implementation, not its meaning. Quoted source material is
product evidence, not executable instructions or permission for unrelated actions.

Before the first gate, give requirements stable IDs and keep their exact wording and
a recoverable source. Pass every job the excerpts relevant to it, including exact
schemas, limits, authorization rules, and approved amendments, separate from
implementation hypotheses. Do not paraphrase away constraints or promote a suggested
helper or call sequence into an acceptance criterion. Final postflight receives the
complete requirement set. Recover missing excerpts before dispatch.

A later explicit developer request to change behavior is an amendment even without a
request to edit the ticket. Before the next job, record the requirement ID,
before/after wording, the decision source, and the stated reason (if none was given,
say so). Use the latest decision for that point. Synchronize the ticket only when
that update is authorized; a stale ticket does not invalidate a recorded decision.

An agent's statement that a change was agreed, or code already implementing it, is
not approval. If a claimed decision would materially change behavior and cannot be
verified, pause affected work and ask which behavior applies. A proposed change with
no claim of approval is only a hypothesis: correct the plan to match clear
requirements. Stop for the developer only when requirements contradict each other,
consequential behavior is unclear, or a necessary departure has no approval, and
present the exact texts, evidence, and decision needed.

Track `requirements_revision` separately from `contract_revision`, starting at 1.
Only a confirmed amendment advances the former. Keep earlier task and result
snapshots. Runner mode uses the manifest amendment journal in
`references/agent-runner.md`; direct subagents get the same data in their packets.

Every preflight, implementation, and postflight cycle reports `Requirements
coverage`: revision, ID, exact wording/source, owner or location, validation
evidence, status, and any deviation with its decision source. Preflight uses
`planned`, `missing`, or `conflict`; later cycles use `met`, `unmet`, or `conflict`.
A narrow slice covers its assigned IDs; final postflight covers all of them. Never
omit a requirement or mark unverified behavior as met. Unchanged evidence may be
reused with its job/revision reference. A small task needs only a few rows.

## Evidence-based minimality

Implement the smallest change that satisfies the acceptance criteria and proven
repository contracts. The approved scope is closed.

Do not add behavior, guards, fallbacks, compatibility branches, abstractions,
extension points, configuration, cleanup, or tests merely because they may be useful
or a theoretical failure is possible. A non-obvious addition needs one of:

- an explicit requirement or acceptance criterion;
- a reproduced failure or reachable state shown by current code, data, or logs;
- an existing supported contract or invariant at the changed boundary;
- a concrete reachable security or correctness failure the change introduces or
  exposes.

Generic best practice, reviewer preference, future use, and "defense in depth"
without a demonstrated path are not evidence. Ask the user only when resolving a
concern would change required behavior or scope.

A fix must not add a mechanism. When a finding comes from code no requirement needs,
remove that code instead of patching it.

Prefer an existing code path, a local edit, and deleting superseded code. Do not mix
in adjacent cleanup. Keep defensive behavior that protects a proven contract unless
the task changes it. Tests prove requested behavior or an observed regression.

Smallest diff does not mean smallest coverage. Inspect the feature's established
tests and artifacts across layers, complete missing supported variants in an existing
story or fixture matrix when the requested behavior needs them, and reuse adequate
coverage. A passing suite without the new scenario is not adequate evidence.

## Reduction Pass

A dedicated step that only removes code. It is mandatory for every implementation
task and never adds behavior, tests, or validation. Run it after the writer stops
and focused validation has run, before the first postflight, and again before any
postflight that follows a `substantive` or `replan` fix:

1. Dispatch a fresh `code-simplicity-review` job on the other vendor at the
   postflight minimum model/effort, with the requirements and amendments with IDs,
   the requirements revision, the full task diff against base inline (a sandboxed
   reviewer may be unable to run `git`), the worker report, and validation results. Do not give it the hypothesis or prior reasoning.
2. Return a non-empty cut list to the same writer responsibility as a `reduction`
   change: apply exactly the listed cuts, add no new code except a call to the named
   helper, and rerun affected validation. Main may decline a cut only with concrete
   evidence that it changes required behavior or breaks a check.
3. Never apply a requirement-changing cut. Report it to the user only when it would
   materially shrink the change.
4. Pass the ledger, applied cuts, and declined cuts with their evidence to postflight.

A `reduction` change needs no fresh preflight, keeps the contract revision, and
consumes no review round. One pass per candidate is enough. If a cut breaks
validation, revert it and record it as declined.

## Delegation Backend

Select one backend at the start and report it in the first progress update with the
model policy:

- `runner` by default;
- `subagents` only when the user explicitly asks, including "не используй runner",
  "не используй ранер", or "используй сабагентов";
- a later explicit instruction changes the backend only after every active job
  stops; record the switch and keep completed evidence.

Never infer the fallback from runner unavailability, a failed job, difficulty, or
convenience. The runner path fails closed unless the user chooses the fallback.

For `runner`, read `references/agent-runner.md` completely before the first job and
dispatch every gate, worker, and specialist through one `agent-runner` process and
YAML artifacts, not subagent tools. Main stays the semantic orchestrator.

For `subagents`, spawn roles with explicit model/effort, `fork_turns: "none"` or
bounded history, and compact self-contained packets; follow up with the same live
gate or writer when applicable. Create no run manifest. Use `agent-runner` only for
other-vendor jobs.

Later instructions to dispatch or ask a role use the selected backend. Gates,
evidence, independence, loops, and lifecycle rules are identical across backends.

Pass an explicit model and effort for every job; do not rely on inherited defaults.
Every job gets a compact self-contained packet.

## Routing Matrix

Use one matrix for every run, including retries and resumes. `$develop-task D` is a
compatibility alias. Reject the removed `$develop-task A` before delegation. Include
the relevant routing rules in every job packet. Choose the requested model/effort
from the matrix, then apply any ceiling to the model only.

For the main chat, recommend `gpt-6.1-sol` low when coordinating a clear approved
plan and medium when main must resolve substantive technical choices; keep the
user's selection. Delegate difficult judgments to the gate tier.

Use `gpt-6-luna` medium for bounded exploration and factual lookup, such as locating
files, tracing an established flow, or extracting facts from documentation, and Luna
high to correlate several sources on a clear question. Architecture, security, difficult
root-cause, and other decision-determining questions use the requesting gate's tier or
higher for their own risk.

Do not create an agent job solely to run a known deterministic command. After the
writer stops and mutation ownership is clear, main runs it. If an agent is needed
only to choose a check or classify a deterministic log, use `gpt-6-luna` low or
medium unless the interpretation carries the task's risk.

If an approved model or role is unavailable, do not silently downgrade. In `adaptive`,
use an equivalent or stronger approved route, repeating preflight if the profile
changes materially. Under a ceiling, stop when no approved route remains.

Judge routing from runner artifacts, without a second telemetry system: a cheaper
writer succeeds only if it reduces usage without more conceptual failures or cycles.

## Model Ceiling

The default policy is `adaptive`, with no ceiling. When the invocation or the user
sets one, as `E <model>`, `M`, or a plain-language limit such as "не выше Sol" or "не
используй сильные модели", read
[`references/model-ceiling.md`](references/model-ceiling.md) before the first job.
Never select a model above a ceiling and never ask the user to raise it.

## Cross-Vendor Review

The home vendor hosts main: GPT in Codex, Claude in Claude Code. Preflight, workers,
discovery specialists, and specialists that preflight requests run on it. Every
`postflight-review`, `diagnosis-review`, and Reduction Pass job, and every specialist
that postflight or diagnosis requests, runs on the other vendor at the peer of the
matrix model, with the same effort. A reviewer from another family does not share the
writer's blind spots; this never raises the review tier.

| GPT model | Claude peer |
| --- | --- |
| `gpt-6-luna` | `claude-haiku-5-5` |
| `gpt-6.1-terra` | `claude-sonnet-5-5` |
| `gpt-6.1-sol` (or a pinned `gpt-6-sol`) | `claude-opus-5-5` |
| `gpt-6-astra` | `claude-fable-5-1` |

Other-vendor jobs always run through `agent-runner`, are always one-shot, and follow
`references/agent-runner.md`: registered in the manifest in runner mode, one private
task file without a manifest in subagent mode, with the ceiling applied first. Return
a specialist report or a challenge to a fresh job for the same gate with the complete
prior gate report.

Before the first job, confirm the other vendor can start, and report cross-vendor
review with the backend and model policy. If it is unavailable, stop and ask; never
move a review to the home vendor silently.

The one exception is exhausted usage: when an other-vendor job or the startup check
fails because the account is out of usage, credits, or quota or is rate-limited (for
example "usage limit", "hit your limit", "rate limit", "quota", "429", "insufficient
credits"), do not wait or retry that vendor. Rerun the job as a fresh home-vendor job
with the matrix model and effort, and keep later cross-vendor jobs there until the
user says otherwise. Say so in the next update, mark each job `home-vendor fallback:
usage limit` in the usage table, and report it. The reviewer still gets a fresh
context, never the writer's conversation. Missing CLIs, authentication failures, and
other errors are not this exception.

The user may turn cross-vendor review off in plain words ("без кросс-ревью", "review
on Codex only"); record it and run those jobs on the home vendor with the matrix model.

## Ownership Invariants

- Main owns orchestration, gate challenges, integration, and lifecycle actions, and
  inspects actual status, diff, and validation rather than trusting summaries.
- Main never silently overrides a gate, and never treats a specialist's report as the
  gate decision.
- In runner mode, every implementation, including Fast, goes through an
  `implementation-worker` job. In subagent mode, main writes product code only when
  preflight confirms Fast and main already holds the required context inside one local
  ownership boundary.
- Use the one generic `implementation-worker` role; add no language-specific workers
  without a demonstrated responsibility or tool-surface boundary.
- One authorized worktree mutator at a time. Stop the current writer and transfer
  ownership before another writer starts, and do not edit while one is active.
- Explorers, gates, and specialists stay read-only.
- `implementation-worker` never commits, pushes, opens a PR, updates external systems,
  or resolves review threads.

## Repository Context

Read applicable `AGENTS.md` files and inspect
`git status --short --untracked-files=all` before routing. Stop before carrying
unrelated or overlapping user changes into the work when isolation is unsafe.

If the repository root contains `front/projects/bakery` plus either
`front/projects/chat` or `back/projects/bakery`, read `references/ui-bakery.md` before
preflight. Pass only relevant repository guidance into job packets.

## Execution Profiles

Build a preliminary profile after minimal inspection. Treat Deep as Critical when it
combines costly, difficult-to-reverse, or difficult-to-validate risks. `Critical`
describes impact and reversibility; `Exceptional` describes reasoning difficulty
beyond Critical, needs recorded evidence, and is never chosen merely for touching a
critical domain. Critical indicators include security, authentication, permissions,
billing, persistence, migrations, destructive behavior, concurrency, public contracts,
and low-validatability changes.

| Profile | Use when | Preflight | Implementation | Postflight (other vendor) |
| --- | --- | --- | --- | --- |
| Fast | Clear local behavior, established pattern, low blast radius, narrow validation | `gpt-6.1-sol` medium | Runner worker on `gpt-6.1-terra` medium; direct fallback uses main or a Terra worker | `gpt-6.1-sol` low |
| Standard | Clear requirements with non-trivial but bounded implementation | `gpt-6.1-sol` medium | Worker on `gpt-6.1-terra` high | `gpt-6.1-sol` medium |
| Deep | Cross-layer, novel, ambiguous, high-risk, or difficult to validate | `gpt-6.1-sol` high | Worker on `gpt-6.1-sol` high by default; `gpt-6.1-terra` high for a visual or prose slice | `gpt-6.1-sol` high |
| Critical | Multiple critical risks, costly failure, low reversibility, or failed lower-tier reasoning | `gpt-6.1-sol` xhigh | Bounded known-pattern slice on `gpt-6.1-sol` high; use xhigh for the exact slice with combined critical factors; `gpt-6.1-terra` high for a visual or prose slice | `gpt-6.1-sol` xhigh |
| Exceptional | Evidenced novel, coupled, difficult-to-validate reasoning beyond the Critical route, or a prior Sol conceptual failure | `gpt-6-astra` high | `gpt-6.1-sol` high for ordinary bounded slices; `gpt-6.1-terra` high for a visual or prose slice; Astra high for the exact exceptional slice | `gpt-6-astra` high |

A visual slice is UI work on an established pattern accepted by rendered output. A
prose slice delivers mainly text for people. Agent instructions and prompts are logic,
not prose. Terra is a writer and visual-check model; gates, diagnosis, and
decision-determining questions stay on Sol or Astra unless a ceiling caps them.

Fast and Standard work use one implementation job. For a preliminary Deep, Critical,
or Exceptional task, when the source scope has Delivery slices, and before any
promotion or diagnosis job, and when preflight upgrades a task to slices, read
[`references/routing.md`](references/routing.md).

## Gates and roles

Preflight confirms or upgrades the lane, critical flags, writer, implementation
model/effort, postflight minimum, and replan triggers, naming one exact route. It
also gives the minimal design: the approach, the existing code it reuses, and a size
budget of rough production and test lines with the test scenarios. When it flags a
requirement whose cost is out of proportion to its outcome, ask the developer before
implementation; never drop it silently. With a
ceiling, it states the requested and the capped model and must not ask to remove the
ceiling. Implementation starts only on `Decision: proceed` and `Routing status:
confirmed` with no unresolved Blocking specialist request. `upgrade required` means
`revise first`: rerun preflight at the upgraded tier.

Postflight classifies the next mutation:

- `none`: nothing to change; required for `Approval: yes`;
- `mechanical`: one obvious local correction with no new decision, coordinated edit,
  or behavior, contract, validation, or profile change; same revision;
- `reduction`: only deletions, merges of duplicate tests, inlining, replacement with a
  named helper, or restoring a wrong cut, in any number of files, with no behavior,
  contract, or validation-obligation change; same revision and writer;
- `substantive`: a non-trivial fix inside the task boundary; new revision and fresh
  preflight;
- `replan`: owner, scope, behavior, contracts, critical risks, validation obligations,
  or profile changed; new revision and fresh preflight.

Except for `reduction`, anything beyond one deterministic correction is `substantive`,
also when uncertain. `Preflight Required` is `yes` exactly for `substantive` and
`replan`; main may add a preflight but never waive one. Return a missing or inconsistent
classification to postflight for correction.

Revision 1 covers the initial implementation. Return a first `mechanical` fix to the
same writer responsibility and tier. A later fix in runner mode is a fresh job with the
prior result, diff, validation, findings, revision, and approving preflight job.

Outside explicitly embedded discovery, specialists run only when a gate requests them
for a concrete question: `repo-practice-review`, `best-practice-review`, `test-review`,
and `code-simplicity-review` (on a plan; on the diff it already runs as the Reduction
Pass, so a gate requests it there only for a new question).

## Workflow

1. Confirm one current task. From a list, work only on the current coherent item.
2. Establish requirements and amendments (Requirements Fidelity), and apply the ticket
   title rule. Do not stop just because the ticket lags a confirmed decision.
3. Read repository instructions, inspect the dirty tree and branch, and gather minimal
   ownership, pattern, reproduction, and validation context.
4. Build the preliminary profile and, only for a multi-area Deep or higher task, an
   ordered slice plan. Complete explicitly selected brainstorm discovery first.
5. Dispatch `preflight-review` with the request, profile, current model/effort, task
   boundary, dirty-tree notes, likely files, constraints, expected behavior, backend,
   slices or a single-job choice, and hypothesis, plus the requirements revision,
   excerpts, and amendment evidence kept separate from the hypothesis. Include evidence
   for every non-obvious behavior, guard, fallback, edge case, or test.
6. Dispatch only the specialists preflight requests, with explicit model/effort, and
   return their raw reports to that gate.
7. If preflight requires a stronger tier, rerun it. Resolve `revise first` or `blocked`.
8. Build the Implementation Contract, or ordered slice contracts.
9. Dispatch one `implementation-worker` per slice, sequentially, with the approved
   route, unless main may write the change itself under Ownership Invariants.
10. After each slice, handle `implemented`, `replan_required`, or `blocked`, and inspect
    its coverage, interfaces, diff, and validation. Give the next writer the exact
    requirements, prior contracts, and produced interfaces. Do not start the next slice
    or expand the task after a replan trigger.
11. Inspect status and diff. Run or verify focused validation and record failed,
    unavailable, and skipped checks. The writer should run checks that may write files
    before returning when its sandbox allows. Run Main validation and any check the
    writer reported as not run. Transfer mutator ownership before a check that may update
    snapshots, generated files, lockfiles, or other artifacts, then inspect the diff.
    Send long output to a file in a private temporary directory and read only its summary
    and failures.
12. Run the Reduction Pass and rerun affected validation. If the reduced diff is
    still about 1.5 times the size budget or more, return to preflight with the
    overrun before postflight: it approves a larger budget with a reason, or sends
    the work back to simplify.
13. Recalculate the postflight floor from the request, profile, actual diff, deviations,
    and validation gaps. Prepare any selected review-task audit under
    `references/composed-workflows.md`.
14. After all slices finish, dispatch `postflight-review` on the combined change on the
    other vendor with the task packet, preflight
    decision, writer result, changed files, the diff inline, validation, cycle, shared round count,
    contract revision, approving preflight, prior findings and fixes, the Reduction Pass
    record, the full requirements and amendments, and the worker's coverage. Require
    independent source-to-diff verification.
15. Return requested specialist results to postflight. A Blocking request still open
    makes approval impossible.
16. Relay postflight findings in the main chat before any writer resumes (Postflight
    Relay).
17. Follow the next-change class, rerun affected validation, and repeat postflight after
    every mutation, within the Bounded Review Loop.
18. If a fix leaves the same failure unresolved, follow Repeated Failure Diagnosis.
    Otherwise promote or replan after a repeated conceptual failure, low confidence, or
    unexpected scope or risk growth.
19. After approval, make logical commits and a draft PR for standalone work unless the
    user asked to stay local. In embedded mode, defer lifecycle to the outer workflow.
20. Report the final state.

## Implementation Contract

Give the writer a compact self-contained packet:

```text
Goal:
Requirements revision:
Source requirements: stable IDs, exact excerpts, and source references.
Confirmed amendments: affected IDs, before/after, decision sources, and reasons.
Acceptance criteria:
Owned paths/responsibility:
Slice dependencies: prior slices or `none`.
Interfaces consumed: exact behavior or contracts from earlier slices, or `none`.
Interfaces to produce: exact behavior or contracts later slices may rely on, or `none`.
Out of scope:
Relevant repository evidence:
Evidence for non-obvious behavior:
Contracts to preserve:
Implementation hypothesis:
Size budget: rough production and test lines, and the test scenarios.
Dirty-tree constraints:
Writer validation:
Main validation:
Replan triggers:
Expected return:
```

Split validation before dispatch. Writer validation holds only checks that can run in
the writer's sandbox. A runner writer has no network, and its sandbox may also block
local sockets and Docker; checks that need them go to Main validation.

Everything is strict except the hypothesis: the writer may adjust local code shape,
naming, helpers, and test structure within the contract. Assign exact paths and remind
it that other changes may exist. The role file defines its response format and replan
triggers: any need beyond or different from the packet, such as changed behavior,
owner, dependency, or critical contract, materially more files, an unsupported product
assumption, or intentionally weakening validation.

A check the writer cannot run is neither `blocked` nor `replan_required`: it finishes
the edits, reports the check as not run, and main runs it.

## Repeated Failure Diagnosis

When one attempted fix leaves the same observable test, runtime, UI, or CI failure
unresolved, or repeated evidence undermines the causal hypothesis, make no more
speculative edits. Stop the writer, keep the exact reproduction and output, and dispatch
a fresh read-only `diagnosis-review` with the failed hypothesis and edit, current diff,
commands, logs, and relevant DOM, state, request, or runtime observations. Gather runtime
evidence the reviewer cannot reach yourself.

The diagnosis labels its cause `confirmed`, `probable`, or `unknown` with evidence that
separates it from rejected hypotheses. No new implementation job on `unknown`. A confirmed
or well-evidenced probable cause becomes a fresh contract revision through preflight.

This does not apply to a clearly different failure, a proven transient infrastructure
error, or a first failure whose cause is already established.

When a worker returns `replan_required`, keep its evidence and diff, stop expansion, and
return to preflight if owner, boundary, behavior, risk tier, or contracts changed; a
local technical adjustment inside the contract only updates the packet.

## Promotion Policy

- First local finding: keep the writer responsibility and follow the next-change class.
- Repeated conceptual finding, low confidence, or unexpected risk or scope growth: stop
  the writer, return to preflight if the profile is invalid, promote the model/effort,
  and give the new writer a fresh packet with the diff and findings. Under `adaptive`, do
  not stay below an evidence-based promotion; under a ceiling, record it and stay capped.
- A different small finding later does not by itself require promotion. Ordinary lint,
  type, build, or test failures are not promotion reasons.
- Writer returned no edits or clearly incomplete work with no named obstacle: main decides
  whether to retry or promote within any ceiling and records it. With an unchanged
  contract and profile this needs no fresh preflight and consumes no round.
- Promotions and replans do not reset the Bounded Review Loop.

## Bounded Review Loop

Keep one task-wide count of unsuccessful final review rounds for postflight and any
embedded review-task audit. A round counts once, after its specialist inputs and
challenges are resolved, when it still requires an in-scope implementation, test, or
artifact correction, even a different one than before. A round whose only correction is
`reduction` does not count; neither do gate continuations, transport retries, pending
specialists, read-only evidence gathering, or declined observations.

If the third round still requires correction, stop before another writer, fix preflight,
or publication and report `needs_user_input` with the diff kept, the remaining findings,
their scope and origin, the attempted fixes, and the decision needed. Do not claim
approval.

Carry the count and prior findings across revisions, models, writers, backends, resumes,
and outer stages. Only an explicit user decision can authorize more rounds or establish a
new task. Diagnosis and fresh-preflight rules grant no extra rounds.

## Delegation Rules

After a gate requests a specialist, that gate owns its interpretation: which specialist,
the exact question, required artifacts, and blocking or advisory. Gates never delegate
recursively. Main picks the model/effort from the Execution Profile and dispatches on
the gate's behalf.

Do not expand, rewrite, or adjudicate a request. Return the raw report to a fresh gate
job with the complete prior gate report in runner mode, or to the same live gate in
subagent mode, with the relevant requirements. A gate cannot approve a product change on
the developer's behalf. When specialists conflict, the gate decides explicitly: follow
repository practice, depart from it, take a transitional fix, or stop for the user.

In runner mode, every follow-up, specialist, fix, and postflight cycle gets its own
immutable job directory; continuity comes only from packets, results, repository state,
and handoffs.

## Silent Long-Poll Discipline

Wait quietly on every running job, test, build, CI, preview, and review refresh. Use one
blocking command or tool call; add no custom monitor or polling script. With a known
GitHub Actions run ID, use `gh run watch <run-id> --exit-status` and stay on it. Continue
a yielded handle with the longest wait the host allows, up to five minutes, and repeat
silently. Report only a stage change, terminal result, needed decision, or transport
problem. Do not inspect processes, logs, or heartbeats just to prove work is alive. If
status must be polled, wait five minutes between queries. A user status request permits
one snapshot.

## Embedded And Lifecycle Policy

Another explicitly invoked workflow wrapping `develop-task` is the outer lifecycle
controller unless the user says otherwise. Engineering gates, routing, ownership,
validation, and approval stay here. Do not commit, push, edit a PR, update trackers, wait
on CI, or resolve threads unless the outer workflow delegates that action; the ticket
title rule is the one exception.

Approved standalone work normally ends with a branch when needed, logical commits, push,
and a draft PR. Create no PR for analysis-only, no-op, blocked, unsafe dirty-tree, or
unapproved work, or when the user asks to stay local.

Before committing, the implementation is complete, validation ran or skipped checks are
documented, postflight approved, and task changes can be isolated. An explicit request to
proceed after `Approval: no` ends this workflow as unapproved and triggers no commit,
push, or PR here.

Any implementation-affecting mutation after approval, including a rebase resolution,
generated file, formatter rewrite, or test-produced artifact, invalidates it: inspect the
diff, rerun affected validation, and get fresh postflight approval. Anything beyond one
deterministic correction, including voluntarily accepting a Recommended or Optional
change, also needs a new revision and fresh preflight before editing.

## Terminal-State Gate

The final response ends the turn; it is never a progress update or a promise. Before it,
verify that:

- no job, command, validation, CI watch, or required wait remains active;
- no in-scope action can be taken without new user input or external state;
- a successful implementation has current postflight approval and no later mutation;
- runner mode has a reconciled `run.yaml` with no `pending` or `running` job and a
  terminal status, unless that itself is the reported blocker;
- the response names one honest state: `completed`, `blocked`, `needs_user_input`, or
  `stopped_by_user`.

If it would say "I will retry", "still running", or similar, do that work or keep waiting.
`invalid_task`, a failed validation, a rejected hypothesis, or an unapproved postflight is
not a blocker while a safe next action remains. If the user said to ignore a time limit,
elapsed time is not a blocker. A required approval, missing product decision, exhausted
loop, unavailable mandatory component, unsafe dirty-tree conflict, or unchangeable external
state may be; state the exact condition and decision needed.

## Postflight Relay

After every postflight response, report in the main chat:

- Blocking findings, or `none`;
- Recommended findings accepted or declined with a reason, or `none`;
- notable Optional findings, or `none`;
- Validation gaps, or `none`;
- Failure class and routing recommendation;
- Next Change Class, whether fresh preflight is required, and why;
- current contract revision and approving preflight job;
- requirements revision, coverage gaps, and confirmed amendments, or `none`;
- Approval and review cycle.

## Agent Usage At Handoff And Completion

Give a concise cumulative usage summary at each handoff and in the final report, with the
matrix, profile, and any ceiling. Use one table: job ID/role, actual model/effort, status,
attempts, uncached input, cached input, output. Account for every launched job, including
failed and retried ones. Show reasoning as a breakdown of output, and keep cache writes
separate when supplied. If the source's input includes cached input, subtract it for the
uncached column.

Add totals for jobs, attempts, tokens, and fix/review cycles, counting each job once and
never summing earlier summaries; the runner's aggregate already sums attempts. Report main
separately when available. Show unavailable values as `n/a`, not zero, and disclose
partial totals; zero-initialized runner counters do not prove zero use. Use runner results
and the reconciled manifest, or available subagent telemetry, with no separate telemetry
system. Keep job IDs and paths in internal handoffs, but put no `run.yaml` path in the
user-facing report. Estimate cost only with a known tariff, label it, and never infer
subscription percentages from tokens.

## Report Format

When done, report:

- Problem and cause, when applicable;
- Execution Profile and writer;
- model policy and any jobs whose requested model was capped;
- Fix;
- Validation and skipped checks;
- Preflight and postflight results and cycle count;
- Reduction Pass: cuts applied and declined, and lines removed;
- implementation-contract revisions and their approving preflight jobs;
- Replans or promotions, or `none`;
- delegation backend, routing matrix, cross-vendor review state, and the Agent Usage
  summary;
- ticket title: old and new, already conforming, or why it was not renamed;
- PR URL/state, or why no PR was created;
- branch and uncommitted/committed/pushed state;
- whether user approval or another decision remains;
- improvement suggestions, only when this run shows friction: a command or context that
  was hard to find, an instruction that was wrong or stale, a mistake a check could have
  caught, or a correction the user says they have given before. For each, say what
  happened, what to change, and where. Prefer a lint rule, type, test, or CI check; propose
  a written rule only when no tool could catch it. Trace each to a specific moment of this
  run, change nothing yourself, and omit this item when there is none.

Keep the final response concise and concrete.
