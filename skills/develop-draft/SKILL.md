---
name: develop-draft
description: "Build a working repository prototype quickly: good code, independent final review, a small validation budget, and a draft PR. Use for `$develop-draft`, `/develop-draft` in Claude Code, or an explicit request for a quick prototype with minimal testing."
---

# Develop draft

Deliver a working prototype with full code quality, requirements fidelity, and
independent review, but no new tests, broad validation, or runner
administration. This is a separate workflow, not `develop-task`'s Fast profile.

## Runtime and ownership

Use direct subagents in both Codex and Claude Code. Do not invoke `agent-runner`
or create its manifests. In Claude Code, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md)
before anything else, including the entry task title, for tool, model, effort,
ceiling, and task-title mappings. This skill defines the workflow;
the adapter supplies runtime mechanics only. Do not load the full
`develop-task` workflow or inherit its test or runner defaults.
Read applicable `AGENTS.md` and, in Claude Code, `CLAUDE.md` instructions.

Main owns framing, routing, validation, and integration. Every profile gets a
fresh `draft-review` final reviewer that is neither the writer nor the
preflight reviewer. One writer at a time; stop it before main runs commands
that can change files. Workers cannot commit, push, publish, change tickets, or
delegate. Never revert or include unrelated user changes. If a required
reviewer or delegation tool is unavailable, report the exact blocker; main's
self-review is no substitute.

## Task title

At entry, read [`../chat-title/SKILL.md`](../chat-title/SKILL.md) and follow it with
the type `draft`. `D` requires final approval of the current diff and completed Delivery: the draft PR
and applicable ticket link, the requested local-only result, or the handoff to an
outer workflow that owns publication. It does not mean production-ready or merged.

## Prototype contract

Inspect repository status and only the code needed to locate the change and its
patterns, then prepare one packet for gates and writer:

```text
Workflow: develop-draft
Goal and observable demo:
Requirements revision: start at 1; increment only for confirmed user amendments.
Source requirements: IDs, exact relevant wording, source, confirmed amendments.
Acceptance criteria:
Owned paths and single writer:
Existing helpers, patterns, and contracts to preserve:
Out of scope and dirty-tree constraints:
Profile, exact models/efforts, model ceiling:
Implementation hypothesis:
Validation: selected checks, optional existing quick test, demo, total budget.
Delivery: repository/base branch, known ticket or none, existing task PR or none,
          draft PR by default; explicit local-only instruction or outer owner.
Replan triggers:
```

Keep source requirements separate from the implementation and never drop
behavior to ease the prototype; only explicit user decisions amend them. Reuse
real components; no duplicates, speculative abstractions, adjacent cleanup,
suppressed errors, disabled checks, or fake success. Use mocks or in-memory
substitutes only if the demo allows, stating their limits. Keep real
authorization, data protection, and critical contracts intact. A secondary
feature the user scoped out may stay unfinished; a defect in the agreed demo is
a finding. Source review does not verify runtime behavior.

## Routing matrix

`develop-task`'s model tiers, delegated directly. `Sol` is `gpt-6.1-sol`,
`Terra` is `gpt-6.1-terra`, `Astra` is `gpt-6-astra`.

| Profile | Evidence | Preflight | Writer | Final review |
| --- | --- | --- | --- | --- |
| Fast | Local, clear behavior and established pattern | Main checks plan; no agent gate | Main or Terra medium | Sol low |
| Standard | Non-trivial but bounded implementation | Sol medium | Terra high | Sol medium |
| Deep | Cross-layer, novel, ambiguous, or hard to validate | Sol high | Sol high | Sol high |
| Critical | Combined critical contracts, costly failure, or poor reversibility | Sol xhigh | Sol high; xhigh for the exact combined-risk responsibility | Sol xhigh |
| Exceptional | Coupled novel reasoning beyond Critical, or an evidenced Sol conceptual failure | Astra high | Sol high; Astra high for the exact exceptional responsibility | Astra high |

In Deep or higher, a visual (UI on an established component pattern) or prose
(documentation, user-facing copy) responsibility may use Terra high. Final
review stays on the home vendor, never cross-vendor.

Main routes Fast after checking its plan against repository evidence;
preflight routes the rest. Fix the exact writer and final-review model/effort
before implementation. Fast is clear, local, reversible work with no changed
critical contract or consequential uncertainty, never a way to skip preflight.
New ambiguity, wider scope, or a critical-contract change promotes to Standard
or higher, with preflight before the affected edits. Critical impact alone is
not Exceptional; a deterministic lint or build failure does not promote. Prefer
a capable writer to more agents: one job per coherent prototype, never split
small work. If the demo spans responsibilities that cannot share one packet,
preflight sets ordered, bounded slices with explicit interfaces; writers stay
sequential and final review covers the combined diff.

Ceilings cap every job: `E <model>` explicitly, `M` at the invocation-turn main
model; default adaptive. Codex order: Luna < Terra < previous `gpt-6-sol` < Sol
< Astra; Claude uses the adapter's. Take the lower of matrix model and ceiling
at the same effort; report requested and selected models when capped. Resolve
an unknown `M` from runtime evidence or ask before delegating. Never guess,
drop, or ask to raise a ceiling. Spawn fresh agents with explicit model, effort,
and a self-contained packet (`fork_turns: "none"` in Codex, a fresh Agent call
in Claude). Main writes a Fast change only if its own model is within the
ceiling, else a capped worker does. Never change the user's main model.

## Validation budget

Default for main, writer, and reviewers:

- Write or update no tests, fixtures, or stories just for coverage; requested
  UI assets stay in scope. Reading existing tests is fine.
- Run `git diff --check`, inspect the full diff, and add at most two targeted
  checks, preferring one short check of the changed flow: changed-file lint,
  affected-package typecheck, a narrow build, or one relevant existing quick
  test (no new setup, better evidence than the alternatives, precise verified
  selector; none if the user prohibits all tests). No suites, E2E, screenshot,
  coverage, or CI jobs, directly or through composite commands.
- About two minutes per candidate for all of it, including startup and demo. No toolchain
  installs, containers, or workspace builds to validate; stop a slow check at a
  safe boundary and report what is unchecked. This limits checks, not
  implementation or reasoning.
- One short manual demo when a local runtime is easy to use; inspect rendered UI
  when feasible. No extensive browser script or temporary harness.
- Reuse passing evidence until relevant code changes, then rerun only affected
  checks. Fix a failing selected check or show it is an unrelated baseline
  issue; a timeout is not a pass.

User instructions can amend this. Reviewers may recommend one existing quick
test in place of a check, but not new test work, broad checks, or CI waits.
If a repository rule or changed critical contract needs more evidence, explain
the conflict and pause only the affected work for a scope or validation
decision. Offer a reversible local demo boundary if it meets the requirements,
never as a silent substitute for required real behavior. Never claim production
readiness.

## Execution and review

1. Report scope, profile, runtime/backend, ceiling, and validation plan. Ask only
   for missing product decisions that affect the demo.
2. Standard or higher: a read-only `draft-review` agent (`Phase: preflight`)
   must approve the packet (correct and resubmit a rejected one) before an
   `implementation-worker` gets it with the findings.
3. Implement within the packet; a worker returns its requirements and interface
   report. Stop for a revised plan before changing behavior, ownership,
   dependencies, or critical contracts outside it; report deviations with
   evidence.
4. Inspect the diff, run or reuse the bounded checks, and record exact failures
   and demo observations; missing runtime evidence is a named gap.
5. Give the final reviewer (`Phase: final`) the original requirements, packet,
   diff, any worker report, and check results. It covers correctness,
   requirements, local practice, simplicity, and validation policy without a
   specialist parade, and returns a cut list of unjustified code and tests.
6. Relay blocking findings and gaps before editing; the same writer fixes
   in-scope defects. A fix that changes boundary, behavior, critical contract,
   or profile needs a revised packet, checked by main for Fast and by fresh
   preflight before affected edits otherwise; fixes within the plan need no
   new preflight. After every code change, rerun affected checks and review the
   new diff; approval never carries over. Before approval the same writer
   applies a non-empty cut list exactly, with no new code; revert and explain
   any cut that breaks a check or required behavior. Cuts need no preflight,
   and a cuts-only round is not unsuccessful.
7. At most two unsuccessful final review rounds; then keep the diff and report
   the remaining decision. If a fix leaves the same observable failure, stop
   guessing: get a fresh read-only diagnosis (reproduction, failed hypothesis,
   diff, logs), optionally `diagnosis-review` at the final-review tier within
   the ceiling. An unknown cause needs more evidence. Diagnoses and replans do
   not reset the round budget.
8. After final approval of the current diff, complete Delivery. Claim completion
   only when the demo, draft PR, and applicable ticket link are ready (unless
   local-only or outer-owned) and no job or required check is running.

Add a specialist only for a specific blocking question the gate cannot settle;
main dispatches it read-only with this validation policy and returns its
findings to the gate. Advisory style preferences start no correction cycle.

## Delivery

After current final approval, main commits the task changes, pushes a task
branch, opens a draft PR, and links an already identified ticket without asking
again; invoking this workflow authorizes that. An explicit local-only request
overrides it. If an explicitly invoked outer workflow owns delivery, hand it
the approved result and follow it instead of publishing twice.

- Commit only the reviewed changes, by repository conventions (default: a
  `codex/` branch), never to the default branch, against the actual repository
  and base.
- Check for an existing task PR and reuse a suitable draft; never replace or
  downgrade a ready PR without user direction. Commit, push, then create or
  update the draft PR with behavior, how to try it, limitations, actual checks, and
  skipped validation, never shown as passed.
- For a ticket established by the request or verified context, put its exact ID
  in the PR title and URL in the body, and link the PR through the tracker
  integration or repository convention, preferably natively, unless already
  linked. A merely similar issue is not the target; with no unambiguous target,
  publish without inventing one or blocking.
- Do not change ticket assignee/status, close it, assign reviewers, or send
  comments/messages unless asked; only the native ticket link is in scope.
- In Codex, attach every created or continued task PR with `attach_artifact`
  when available. In Claude Code use the configured GitHub and tracker tools or
  CLIs; Codex-only chat attachments are not a Claude completion gate.
- Do not merge, deploy, or wait for CI; say triggered checks were not awaited.
  Never bypass hooks or required policy to fit the budget; report the conflict.

Missing GitHub or tracker access does not erase finished work: complete
unaffected delivery, report the exact blocker, and give the PR or commit state.
A missing required ticket link is a delivery gap. Never call a local patch the
completed default workflow.

The compact final response states: what works and how to try it; checks and
demo steps passed, failed, or unavailable, whether the quick test ran, and that
no tests were added unless requested; limitations and unverified behavior;
preflight approval or Fast exemption, final-review decision, correction rounds,
roles, and actual models/efforts; draft PR URL/state, ticket link or why none,
branch and commit/push state, and any blocker or pending decision. Report token
usage only if the runtime supplies it; never invent telemetry or build accounting.
