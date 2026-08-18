---
name: develop-task
description: Explicitly invoked engineering workflow for repository implementation tasks with mandatory preflight/postflight review gates, adaptive gpt-5.6-terra/gpt-5.6-sol routing, runner-supervised fresh-context delegation by default, an explicit direct-subagent fallback, focused validation, and standalone lifecycle handling. Use only when the user explicitly writes `$develop-task` or explicitly asks to run the develop-task workflow; otherwise do not select this skill.
---

# Develop Task

## Core Contract

Implement one coherent repository task at a time. Own task framing, model and
agent routing, integration, validation evidence, review coordination, and final
lifecycle actions. Do not invent business requirements.

For every implementation task, including a Fast change:

1. Obtain `preflight-review` approval before the first implementation edit.
   That approval covers one unchanged implementation contract. Repeat preflight
   only when a replan trigger changes or invalidates that contract or its
   Execution Profile.
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

Dispatch `preflight-review` once before implementation under each approved
contract, and dispatch it again after any replan-triggering contract or profile
change. Dispatch `postflight-review` after every resulting implementation diff.
Let the gates own review decisions and resolve specialist conflicts.

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

Use the single generic `implementation-worker` for every runner-mode task, for
Standard and Deep direct-subagent tasks, and for a Fast direct-subagent task
when handoff adds useful separation. Assign exact paths or responsibility and
remind it that other user or agent changes may exist.

Return all first local postflight fixes to the same writer responsibility and
tier. Runner mode creates a fresh implementation job with the prior result,
diff, validation, and findings; direct-subagent mode follows up with the same
live writer. Use a new stronger route only after stopping the current writer
and explicitly transferring ownership.

### Generalist Specialists

Let a core gate request these agents only for a concrete question:

- `repo-practice-review` for repository evidence and local precedent;
- `best-practice-review` for general engineering practice;
- `test-review` for focused validation and test quality;
- `code-simplicity-review` for scope, reuse, and unnecessary complexity;

Do not add language-specific implementation workers. Reconsider specialization
only after repeated real tasks demonstrate a distinct responsibility or tool
surface.

## Workflow

1. Confirm one current task. If the user provides a list, work only on the
   current coherent item.
2. Stop for requirements discovery when expected product behavior or acceptance
   criteria are too unclear to implement without invention.
3. Read repository instructions, inspect the dirty tree and current branch,
   gather minimal ownership, nearby-pattern, reproduction, and validation
   context, and conditionally load repository-specific guidance.
4. Build the preliminary Execution Profile.
5. Dispatch mandatory `preflight-review` with the user request, preliminary
   profile, current preflight model/effort, task boundary, dirty-tree notes,
   likely files, constraints, expected behavior, selected backend and its writer
   invariant, and initial technical hypothesis.
6. If preflight requests specialists, dispatch only the requested read-only
   roles with explicit model/effort and return their raw reports to the same
   gate responsibility for its updated decision.
7. If preflight requires a stronger tier, rerun preflight before editing. If it
   returns `revise first` or `blocked`, resolve that state before continuing.
8. Build the implementation contract defined below.
9. In runner mode, dispatch one `implementation-worker` with the approved
    model/effort for every profile. In direct-subagent mode, let main write only
    when preflight confirms Fast and main already holds the required context
    inside one local ownership boundary; otherwise dispatch one
    `implementation-worker`.
10. Handle the writer result: `implemented`, `replan_required`, or `blocked`.
    Do not materially expand the task without returning to preflight.
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
    cycle, and prior findings/fixes.
14. If postflight requests specialists, return their raw results to the same
    gate for its final classification. Approval is impossible while a Blocking
    specialist request remains unresolved.
15. Relay postflight findings in the main chat before any writer resumes.
16. Return first local blocking fixes to the same writer responsibility using
    the selected backend, rerun focused validation, and repeat postflight.
17. Promote or replan after a repeated conceptual failure, low confidence, or
    unexpected scope/risk growth.
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

When a worker returns `replan_required`, preserve its evidence and current diff,
stop further expansion, and return to preflight if owner, boundary, behavior,
risk tier, or contracts changed. Update only the task packet for a local
technical adjustment that stays inside the approved contract.

## Promotion Policy

- First local blocking finding: use the same writer responsibility and same
  tier. Start a fresh runner job in runner mode; follow up with the live worker
  in direct-subagent mode.
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
before lifecycle actions continue.

## Postflight Relay

After every postflight response, report in the main chat:

- Blocking findings, or `none`;
- Recommended findings accepted or declined with a reason, or `none`;
- notable Optional findings, or `none`;
- Validation gaps, or `none`;
- Failure class and routing recommendation;
- Approval and review cycle.

## Report Format

When done, report:

- Problem and cause, when applicable;
- Execution Profile and writer;
- Fix;
- Validation and skipped checks;
- Preflight and postflight results and cycle count;
- Replans or promotions, or `none`;
- delegation backend and, for runner mode, the `run.yaml` path;
- PR URL/state, or why no PR was created;
- branch and uncommitted/committed/pushed state;
- whether user approval or another decision remains.

Keep the final response concise and concrete.
