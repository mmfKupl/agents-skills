# Develop Task Orchestration Decision Record

## Status

Accepted on 2026-07-31. This is the durable architecture reference for
`develop-task`. The executable algorithm lives in
`skills/develop-task/SKILL.md`; concrete role contracts live in `agents/`.
Keep the invariants and routing policy below aligned with those files, without
duplicating their full operational instructions here.

## Goal

Make the main agent an orchestration and integration layer while assigning
non-trivial implementation to a model selected for the task. Preserve strong
independent review, avoid conflicting writers, and make escalation cheaper than
repeating weak attempts.

Use supervised one-shot runner jobs and YAML artifacts by default so every
delegated role starts fresh and has bounded context. Preserve the previous
direct-subagent behavior as an explicit per-run user fallback.

The workflow handles one coherent repository implementation task. It does not
invent product requirements.

## Decisions

1. `preflight-review` and `postflight-review` are mandatory for every
   implementation task, including Fast work. There is no approved
   `develop-task` path that waives either gate.
2. One preflight approval covers one exact implementation-contract revision.
   Repeat preflight before every postflight-directed fix classified as
   `substantive` or `replan`. Only a deterministic local `mechanical`
   correction may reuse the current revision without another preflight.
3. The main agent owns intent, routing, evidence, gate challenges, integration,
   and lifecycle. In runner mode it delegates every implementation; in the
   direct-subagent fallback it may write code only for a confirmed Fast profile.
4. Use one generic `implementation-worker` role for every runner-mode task and
   for Standard and Deep direct-subagent work. Fast and Standard work normally
   uses one job. A multi-surface Deep or Critical contract may use several
   ordered fresh jobs of that same role, each owning one bounded slice. Do not
   add language-specific workers.
5. At most one agent may mutate a shared worktree at a time. Code writing and
   potentially write-producing validation are serialized through the same
   authorized-mutator state.
6. Review gates and generalist specialists are read-only. Gates request
   specialists; the main agent dispatches them through the selected backend and
   returns raw evidence to the requesting gate for interpretation.
7. Shared custom-agent TOML files do not pin a model or reasoning effort. Every
   consuming workflow selects an explicit callable model ID and effort for each
   delegated job. Runner jobs start fresh; direct-subagent jobs use a no-history
   or bounded-history fork.
8. Writer handoff uses a strict contract boundary and a flexible implementation
   hypothesis. Evidence that invalidates the approved boundary produces
   `replan_required`; local implementation choices do not.
9. Postflight classifies the next implementation mutation as `none`,
   `mechanical`, `substantive`, or `replan`. A first mechanical finding may
   return to the same writer under the current revision. Substantive and replan
   fixes require a fresh preflight and new contract revision before editing. A
   repeated conceptual error, unexpected risk growth, or persistent low
   confidence also causes replan and/or promotion to a stronger model.
10. Any implementation-affecting mutation after approval invalidates that
    approval and requires new diff inspection, affected validation, and
    postflight.
11. Repository-specific owner maps and commands are conditional references, not
    generic orchestration rules.
12. Select one delegation backend per run. `runner` is the default for every
    gate, specialist, and implementation worker. `subagents` is selected only
    by an explicit user instruction not to use the runner or to use subagents.
13. Runner mode uses one private App Server process per immutable YAML job. The
    main thread owns the semantic run plan and prepares task documents; the
    one-shot manifest helper validates each task, creates its immutable job
    directory, atomically registers it, reconciles result-derived execution
    fields, and owns terminal run timestamps in `run.yaml`. Runner processes
    own unique result files. No daemon, MCP server, batch engine, or
    model-driven polling is part of the workflow.
14. Every runner-mode role, including Fast implementation, uses a fresh worker.
    Direct-subagent mode preserves the prior option for main to implement a
    confirmed Fast task.
15. A runner follow-up is a new job with the same role, tier, ownership, and
    explicit prior artifacts. Same-writer and same-gate semantics do not imply
    hidden thread continuity in runner mode.
16. After one attempted fix leaves the same observable failure unresolved,
    stop speculative edits and require a fresh read-only root-cause diagnosis
    before another preflight and implementation mutation.
17. A final response is a terminal-state decision, never a progress update. It
    requires no active work or available next action; runner mode additionally
    requires a reconciled and atomically finalized `run.yaml`.
18. Runner context rotation uses absolute latest-turn token counts rather than
    a percentage of the reported model window. Profile budgets set both soft
    checkpoint and hard interruption thresholds.
19. Live foreground work and post-PR lifecycle checks use five-minute silent
    long polls. Unchanged state produces no commentary or extra status probes.
    Once a GitHub Actions run ID is known, an available
    `gh run watch <id> --exit-status` is the mandatory foreground watcher.
20. The approved task scope is closed. New behavior, defenses, abstractions,
    edge cases, tests, and validation require an explicit requirement, a
    reproduced failure or reachable state demonstrated by current code, data,
    or logs, an existing supported contract, or a concrete reachable
    security/correctness failure at the changed boundary. Hypothetical future
    use and generic best practice do not justify code.
21. Model routing has three run-wide modes. `adaptive` preserves the matrix;
    `explicit_ceiling` (`E`) caps every delegated job at a user-selected GPT-5.6
    model; `main_ceiling` (`M`) caps every delegated job at the model selected
    for the main chat. A ceiling is strict and never triggers a request to lift
    it. Runner mode records and enforces it in `run.yaml`; direct-subagent mode
    checks it before every spawn.

## Execution Profiles

Every delegated job receives one exact model and effort, never a range.

| Profile | Typical shape | Preflight | Implementation | Postflight |
| --- | --- | --- | --- | --- |
| Fast | Established local pattern, low blast radius, narrow validation | `gpt-5.6-terra` medium | Runner worker on `gpt-5.6-luna` medium; direct fallback uses main or a Luna worker | `gpt-5.6-terra` medium |
| Standard | Clear requirements, non-trivial but bounded logic | `gpt-5.6-terra` high | Worker on `gpt-5.6-terra` medium by default | `gpt-5.6-terra` high |
| Deep | Cross-layer, novel, ambiguous, high-risk, or hard to validate | `gpt-5.6-sol` high by default | Worker on `gpt-5.6-terra` high by default | `gpt-5.6-sol` high by default |
| Deep + Critical | Multiple critical risks, costly failure, low reversibility, or failed lower-tier reasoning | `gpt-5.6-sol` xhigh by default | Bounded known-pattern slice on `gpt-5.6-terra` high; evidence-based promotion to Sol | `gpt-5.6-sol` xhigh by default |

Routing adjustments:

- Apply the routing matrix first to obtain the requested model. When `E` or `M`
  is active, select the lower model in the fixed Luna < Terra < Sol order and
  preserve the matrix's reasoning effort. Record both models when they differ.
  Preflight and later promotions do not cross or request removal of the ceiling.

- Raise Standard implementation to `gpt-5.6-terra` high only when preflight
  names concrete reasoning uncertainty, unfamiliar patterns, or difficult
  validation.
- Promote a Deep or Critical implementation slice from `gpt-5.6-terra` high to
  `gpt-5.6-sol` high only for evidence of novel architecture without precedent,
  security/auth reasoning, concurrency, a complex migration, a costly public
  contract, inseparable coupled layers, difficult validation or rollback, or a
  prior Terra conceptual failure. Ordinary tool or test failures do not count.
- Use Sol xhigh for implementation only when several promotion factors combine
  or Sol high has already failed conceptually. Reserve max for exceptional
  quality-first work after a lower Sol tier conceptual failure.
- Do not silently downgrade when a selected model or role is unavailable. Use
  an equivalent-or-stronger approved route or stop explicitly.

Known deterministic validation commands run directly after writer ownership is
released. A log-classification-only agent may use Luna low or medium; semantic
gates retain their configured tier. Diagnosis uses Terra high for Fast or
Standard, Sol high for Deep, and Sol xhigh for a Critical unresolved cause.
Evaluate routing with existing run artifacts: role/model/effort counts,
uncached input and output, cached input, promotions, first-pass postflight
approval, and repeated fix cycles.

Critical indicators include security, authentication, permissions, billing,
persistence, migrations, destructive behavior, concurrency, public contracts,
and low-validatability changes.

## Ownership Model

```text
main orchestrator
  -> optional parallel read-only discovery jobs
  -> mandatory read-only preflight job
  -> one implementation writer job for Fast/Standard
     or ordered bounded writer jobs for an approved multi-surface Deep/Critical plan
  -> focused validation under controlled mutation ownership
  -> mandatory independent read-only postflight job
  -> classify next mutation
     -> mechanical: same revision and writer responsibility
     -> substantive/replan: new revision and fresh preflight before writer
  -> main accepts and performs allowed lifecycle actions
```

Runner mode records that sequence outside the worktree under a private
temporary `run.yaml` plus immutable task/result job directories. A companion
one-shot helper reconciles the manifest after every job and finalizes it before
the main thread ends. Direct-subagent mode uses the collaboration lifecycle
without runner artifacts.

Parallel implementation is unsupported by this design, including across
separate worktrees. It remains deferred until ownership, isolation, integration,
conflict handling, combined validation, and combined postflight mechanics are
specified explicitly.

## Handoff Contract

The writer receives:

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

Strict fields are goal, acceptance criteria, ownership, out-of-scope boundary,
preserved contracts, validation expectations, and replan triggers. The
implementation hypothesis is intentionally revisable inside those boundaries.

The worker returns one of:

- `implemented`: completed inside the approved packet;
- `replan_required`: safe completion requires a boundary or contract change;
- `blocked`: a concrete condition such as dirty overlap, missing context,
  unavailable access, or unavailable approved validation prevents progress.

Replan applies only to a need beyond or different from the approved packet. An
already approved cross-layer change, dependency, or user-visible feature is not
itself a replan trigger.

## Gate Semantics

Implementation starts only when preflight returns both:

- `Decision: proceed`;
- `Routing status: confirmed`.

`upgrade required` implies `revise first`. An unresolved Blocking specialist
request also prevents proceed.

Postflight approval requires no Blocking findings and no unresolved Blocking
specialist request. It reviews the actual diff and validation evidence, not the
writer summary. The postflight model may not be below the effective risk shown
by the final diff.

Every postflight decision also classifies the next implementation mutation:

- `none`: no implementation mutation is required;
- `mechanical`: one deterministic local correction with no new technical
  decision, coordinated edit, contract change, material validation change, or
  profile change; the current revision remains valid;
- `substantive`: a non-trivial fix inside the overall task boundary; create and
  preflight a new contract revision;
- `replan`: the approved boundary, contracts, validation obligations, critical
  risks, or profile changed; create and preflight a new contract revision.

Anything beyond a single deterministic local correction is `substantive`, and
uncertainty resolves toward fresh preflight. The main agent may add a preflight
but may not waive one required by postflight.

`Preflight Required` is `yes` exactly for `substantive` and `replan` and `no`
for `none` and `mechanical`. `Approval: yes` is valid only with `Next Change
Class: none`. A missing or inconsistent classification is an incomplete gate
response and returns to the same postflight responsibility for correction.

Gate challenges are evidence-based and return to the same gate. The main agent
does not silently overrule a gate.

## Failure And Promotion Policy

- First local defect: preserve the writer responsibility when appropriate, but
  route by next-change class. Mechanical fixes reuse the current revision;
  substantive fixes receive a fresh preflight and revision before the writer.
- Repeated conceptual defect: stop the writer, reassess the contract and
  profile, then promote or replace the writer with explicit ownership transfer.
- Same observable failure after an attempted fix: stop edits, capture the exact
  reproduction and failed hypothesis, and run a fresh read-only root-cause
  diagnosis before another preflight or writer job.
- Scope, owner, behavior, or contract drift: `replan_required`, followed by a
  new preflight decision before edits continue.
- Missing requirements: stop for requirements discovery or user input.
- Unavailable mandatory gate: fail closed.
- Three unresolved postflight cycles or five evidence-based gate challenges:
  stop for a user decision rather than looping indefinitely.

## Validation And Approval State

Tests may update snapshots, generated files, caches, or lockfiles. Run such
checks while the current writer owns mutation or after an explicit mutator
transfer. Reinspect status and diff afterward.

Rebases, conflict resolution, formatting, generated-file changes, and tracked
test output after approval all invalidate approval. Any such mutation beyond a
single deterministic local correction also creates a new contract revision and
requires fresh preflight before editing, including a voluntarily accepted
Recommended or Optional implementation change.

## Shared Reviewer Compatibility

The specialist roles are reused by `review-task`, so removing fixed TOML
reasoning defaults requires every caller to route them explicitly.
`review-task` therefore owns its own standard/deep/audit model policy; changes
to these shared roles must check every caller rather than assuming
`develop-task` is the only consumer.

## Repository-Specific Context

UI Bakery guidance lives in
`skills/develop-task/references/ui-bakery.md` and loads only when repository
evidence identifies the monorepo. Other repositories use their own `AGENTS.md`,
nearby code, and local validation commands without paying for Bakery context.

## Scope Deliberately Deferred

- language- or framework-specific implementation workers;
- multiple simultaneous writers in one worktree;
- a numerical complexity score;
- automatic fallback to weaker models;
- replacing independent gates with main-agent self-review.

## Validation Checklist For Workflow Changes

Before publishing a revision:

1. Validate skill frontmatter and metadata.
2. Parse every custom-agent TOML file.
3. Run `git diff --check` and scan for stale fixed-routing or main-only rules.
4. Install into a disposable Codex home and verify the skill, references,
   metadata, and custom roles are copied.
5. Forward-test fresh-context Fast and worker-delegated scenarios, plus replan,
   promotion, Bakery/non-Bakery, and dirty-tree cases when routing/runtime access
   permits.
6. Confirm from traces that every implementation and postflight job names its
   `contract_revision` and exact approving preflight, all required repeat
   preflights ran, the route was exact, and only one authorized mutator existed
   at any moment.
7. Forward-test both delegation selections: default runner jobs for gates,
   specialists, and implementation; and explicit user opt-out to direct
   subagents with no runner artifacts.
