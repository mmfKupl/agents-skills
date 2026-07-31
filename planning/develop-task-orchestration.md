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

The workflow handles one coherent repository implementation task. It does not
invent product requirements.

## Decisions

1. `preflight-review` and `postflight-review` are mandatory for every
   implementation task, including Fast work. There is no approved
   `develop-task` path that waives either gate.
2. One preflight approval covers one unchanged implementation contract. Repeat
   preflight after a replan trigger changes ownership, scope, behavior,
   contracts, validation, or the Execution Profile.
3. The main agent owns intent, routing, evidence, gate challenges, integration,
   and lifecycle. It may write implementation code only for a confirmed Fast
   profile.
4. Standard and Deep work use one generic `implementation-worker`. Do not add
   language-specific workers until repeated tasks show a real responsibility
   or tool-surface boundary.
5. At most one agent may mutate a shared worktree at a time. Code writing,
   write-mode OpenSpec work, and potentially write-producing validation are
   serialized through the same authorized-mutator state.
6. Review gates and generalist specialists are read-only. Gates request
   specialists; the main agent performs the technical spawn and returns raw
   evidence to the requesting gate for interpretation.
7. Shared custom-agent TOML files do not pin a model or reasoning effort. Every
   consuming workflow selects an explicit callable model ID and effort for each
   spawn and uses a no-history or bounded-history fork.
8. Writer handoff uses a strict contract boundary and a flexible implementation
   hypothesis. Evidence that invalidates the approved boundary produces
   `replan_required`; local implementation choices do not.
9. A first local postflight finding returns to the same writer. A repeated
   conceptual error, unexpected risk growth, or persistent low confidence
   causes replan and/or promotion to a stronger model.
10. Any implementation-affecting mutation after approval invalidates that
    approval and requires new diff inspection, affected validation, and
    postflight.
11. Repository-specific owner maps and commands are conditional references, not
    generic orchestration rules.

## Execution Profiles

Every actual spawn receives one exact model and effort, never a range.

| Profile | Typical shape | Preflight | Implementation | Postflight |
| --- | --- | --- | --- | --- |
| Fast | Established local pattern, low blast radius, narrow validation | `gpt-5.6-terra` medium | Main or worker on `gpt-5.6-terra` medium | `gpt-5.6-terra` medium |
| Standard | Clear requirements, non-trivial but bounded logic | `gpt-5.6-terra` high | Worker on `gpt-5.6-terra` medium by default | `gpt-5.6-terra` high |
| Deep | Cross-layer, novel, ambiguous, high-risk, or hard to validate | `gpt-5.6-sol` high by default | Worker on `gpt-5.6-sol` high by default | `gpt-5.6-sol` high by default |
| Deep + Critical | Multiple critical risks, costly failure, low reversibility, or failed lower-tier reasoning | `gpt-5.6-sol` xhigh by default | Worker on `gpt-5.6-sol` xhigh by default | `gpt-5.6-sol` xhigh by default |

Routing adjustments:

- Raise Standard implementation to `gpt-5.6-terra` high only when preflight
  names concrete reasoning uncertainty, unfamiliar patterns, or difficult
  validation.
- Raise Deep from high to xhigh for novel architecture, several coupled layers,
  or substantial uncertainty.
- Use `gpt-5.6-sol` max when multiple critical indicators combine, failure is
  especially costly or irreversible, correctness is difficult to validate, or
  a lower Sol tier has already made a conceptual mistake.
- Do not silently downgrade when a selected model or role is unavailable. Use
  an equivalent-or-stronger approved route or stop explicitly.

Critical indicators include security, authentication, permissions, billing,
persistence, migrations, destructive behavior, concurrency, public contracts,
and low-validatability changes.

## Ownership Model

```text
main orchestrator
  -> optional parallel read-only discovery
  -> mandatory read-only preflight
  -> optional write-mode OpenSpec steward
  -> one implementation writer
  -> focused validation under controlled mutation ownership
  -> mandatory independent read-only postflight
  -> same writer fixes local findings
  -> main accepts and performs allowed lifecycle actions
```

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

Gate challenges are evidence-based and return to the same gate. The main agent
does not silently overrule a gate.

## Failure And Promotion Policy

- First local defect: same writer, same tier, then validation and postflight.
- Repeated conceptual defect: stop the writer, reassess the contract and
  profile, then promote or replace the writer with explicit ownership transfer.
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

OpenSpec drift is repaired by stopping the code writer, transferring mutation
ownership to write-mode `openspec-steward`, synchronizing artifacts, and then
repeating affected validation and postflight.

Rebases, conflict resolution, formatting, generated-file changes, OpenSpec
synchronization, and tracked test output after approval all invalidate approval.

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
6. Confirm from traces that both gates ran, the route was exact, and only one
   authorized mutator existed at any moment.
