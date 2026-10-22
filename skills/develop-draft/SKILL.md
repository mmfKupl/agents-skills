---
name: develop-draft
description: Build a working repository prototype quickly, with good implementation code, independent final review, preflight for non-trivial work, and a small validation budget. Use for $develop-draft, /develop-draft in Claude Code, or an explicit request for a quick prototype with minimal testing. Ordinary implementation requests belong to the normal development workflow.
---

# Develop draft

Deliver a working prototype for the user to try. Keep implementation quality,
requirements fidelity, and independent review. Save time by omitting new tests,
broad validation, runner administration, and publication by default.
This is a separate workflow, not the Fast profile of `develop-task`.

## Runtime and ownership

Use direct subagents in both Codex and Claude Code. Do not invoke `agent-runner`
or create its manifests. In Claude Code, first read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md)
for tool, model, effort, and ceiling mappings. This skill defines the workflow;
the adapter supplies runtime mechanics only. Do not load the full
`develop-task` workflow or inherit its test, runner, or PR defaults.
Read applicable `AGENTS.md` and, in Claude Code, `CLAUDE.md` instructions.
Use [`../unslop/SKILL.md`](../unslop/SKILL.md) for user-facing writing.

Main owns framing, routing, validation, and integration. For Fast work, main
checks the plan against repository evidence and may implement directly, without
a preflight agent. Standard and higher profiles require `draft-review` plan
approval and an `implementation-worker`. Every profile requires a fresh
`draft-review` agent for final code review, independent of the writer and any
preflight reviewer. There is exactly one writer
at a time. Stop it before main runs commands that can change files.
Workers cannot commit, push, publish, change tickets, or recursively delegate.
Preserve unrelated user changes; never revert or include them in the result.
If a required reviewer or delegation tool is unavailable, report the exact
blocker. Do not substitute main's self-review for independent approval.

## Prototype contract

Inspect repository status and only the code needed to locate the change and
its existing patterns. Then prepare one compact packet for gates and writer:

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
Replan triggers:
```

Keep the source requirements distinct from the proposed implementation. Do
not remove behavior to make a prototype easier. Later explicit user decisions
amend the relevant requirements; reviewer preference cannot amend them.
Reuse real project components and ordinary maintainable code. Avoid duplicate
implementations, speculative abstractions, adjacent cleanup, suppressed errors,
disabled checks, and fake success states. Use mocks or in-memory substitutes
only when consistent with the requested demo, and make their limitations clear.
Keep real authorization, data protection, and existing critical contracts intact.

An unfinished secondary feature can be out of scope when the user requested
that scope. An implementation defect in the agreed demo is a review finding.
Do not mark runtime behavior verified merely because source review passed.

## Routing matrix

Use the same model tiers as `develop-task`, with direct delegation and a
smaller validation contract. More agents are not a substitute for choosing a
capable writer. Keep one implementation job for a coherent prototype.

| Profile | Evidence | Preflight | Writer | Final review |
| --- | --- | --- | --- | --- |
| Fast | Local, clear behavior and established pattern | Main checks plan; no agent gate | Main or `gpt-6-luna` medium | `gpt-6.1-sol` low |
| Standard | Non-trivial but bounded implementation | `gpt-6.1-sol` medium | `gpt-6-luna` high | `gpt-6.1-sol` medium |
| Deep | Cross-layer, novel, ambiguous, or hard to validate | `gpt-6.1-sol` high | `gpt-6.1-sol` high | `gpt-6.1-sol` high |
| Critical | Combined critical contracts, costly failure, or poor reversibility | `gpt-6.1-sol` xhigh | `gpt-6.1-sol` high; xhigh for the exact combined-risk responsibility | `gpt-6.1-sol` xhigh |
| Exceptional | Coupled novel reasoning beyond Critical, or an evidenced Sol conceptual failure | `gpt-6-astra` high | `gpt-6.1-sol` high; Astra high for the exact exceptional responsibility | `gpt-6-astra` high |

Main resolves Fast routing; preflight resolves other profiles. Select one exact
writer/model/effort and final-review model/effort before implementation.
Fast requires a clear, local, reversible change with no changed critical
contract or consequential uncertainty. Do not label work Fast merely to skip
preflight. New ambiguity, wider scope, or a critical-contract change moves it
to Standard or higher and requires preflight before the affected edits.
Critical impact alone does not justify Exceptional. A deterministic lint or
build failure does not justify promotion. If the demo crosses responsibilities
that cannot safely share one packet, preflight defines ordered, bounded slices
with explicit interfaces; writers remain sequential and final review covers
the combined diff. Do not split small work just to add jobs.

Honor user model ceilings on every job. Support `E <model>` for an explicit
maximum and `M` for the invocation-turn main model. Default to adaptive routing.
In Codex the order is Luna < previous `gpt-6-sol` < `gpt-6.1-sol` < Astra;
`Sol` means `gpt-6.1-sol`. In Claude use the adapter's order and aliases.
Select the lower of the matrix model and the ceiling, preserving effort;
report requested and selected models when capped. Recover an unknown `M`
from runtime evidence or ask which ceiling applies before delegation. Never
guess, silently drop a ceiling, or ask to raise it because a job is difficult.
Spawn fresh agents with explicit selected model and effort and a self-contained
packet, using `fork_turns: "none"` in Codex or a fresh Agent call in Claude.
Main may write a Fast change only when its actual model satisfies the ceiling;
otherwise select a capped worker. Do not change the user's main model setting.

## Validation budget

Default policy for main, writer, and reviewers:

- Do not write or update automated tests, test fixtures, or stories solely as
  coverage by default. UI assets requested as the deliverable remain in scope.
  Read existing tests when useful to understand a contract.
- Run `git diff --check` and inspect the complete task diff. Choose the smallest
  useful validation: one short check of the actual changed flow is preferable
  to redundant builds or more discussion of the plan. Add at most two targeted
  automated checks, such as changed-file lint, affected-package typecheck, a
  narrow build, or one existing quick test directly relevant to the change.
- The optional test must run without new setup and provide better evidence
  than the alternatives. Use a precise test selector and verify the command's
  scope. It counts toward the same two-check and time budget; it is not an
  extra phase. Do not run test suites, E2E, screenshot, coverage, or CI jobs.
  If the user explicitly prohibits all tests, do not run even this quick test.
  Inspect composite commands so they do not launch broad checks implicitly.
- Aim for a combined validation budget of about two minutes per candidate,
  including automated checks, any quick test, runtime startup, and manual demo.
  Do not install a toolchain, start containers, or run a workspace build just
  for validation. Stop a slow check at a safe boundary and report what remains
  unchecked. This budget limits checks, not implementation or agent reasoning.
- When an existing local runtime is easy to use, perform one short manual demo
  of the changed flow. For UI changes, inspect the rendered result when feasible.
  A short local start is fine within the budget. Do not replace omitted tests
  with an extensive browser script or a temporary test harness.
- Reuse successful evidence until relevant code changes. After fixes, rerun
  only affected checks. A failing selected check must be fixed or explicitly
  identified as an unrelated baseline issue; a timeout is not a pass.

User instructions can amend this policy. Reviewers may recommend replacing a
less useful check with one existing quick test within the same budget; they
cannot add new test work, broad checks, or CI waiting. If an applicable
repository rule requires validation beyond this policy,
or the changed critical contract needs evidence this budget cannot provide,
explain the concrete conflict and pause only the affected work for a scope or
validation decision. Offer a reversible local demo boundary when it meets the
requirements; do not silently substitute it for required real behavior.
Do not claim production readiness from this workflow.

## Execution and review

1. Report the prototype scope, profile, runtime/backend, ceiling, and short
   validation plan. Resolve only missing product decisions that affect the demo.
2. For Fast, check the compact plan yourself and implement without dispatching
   preflight. For Standard or higher, send the packet to a read-only
   `draft-review` agent with `Phase: preflight` and obtain approval before
   implementation. Correct a rejected plan and return it to the gate. Give
   gate findings to the writer with the approved packet.
3. Implement within the agreed ownership and validation policy. A delegated
   worker returns its normal requirements and interface report; main need not
   produce a separate worker report for a Fast edit. Stop for a revised plan
   before changing behavior, ownership, dependencies, or critical contracts
   outside that packet. Report deviations with repository evidence.
4. Inspect the resulting diff and run or reuse the bounded checks. Capture exact
   failures and demo observations. Missing runtime evidence stays a named gap.
5. Dispatch a fresh `draft-review` agent with `Phase: final`, the original
   requirements, current packet, task diff, worker report if any, and check results.
   The writer and preflight agent cannot serve as the final reviewer. Review
   must cover correctness, requirements, local practice, simplicity, and the
   agreed validation policy without adding a specialist parade.
6. Relay blocking findings and validation gaps before another edit. Fix concrete
   in-scope defects with the same writer. Revise the packet when a fix changes
   the boundary, behavior, critical contract, or model profile. When the packet
   needs revision, main checks it if the work remains Fast; otherwise obtain
   fresh preflight before affected edits. Ordinary fixes within the current
   plan do not require another preflight for any profile.
   After every code mutation, rerun affected checks and obtain final review of
   the new diff. Never reuse approval for an older candidate.
7. Allow at most two unsuccessful final review rounds. If the second still
   requires correction, preserve the diff and report the remaining decision.
   If a fix leaves the same observable failure unresolved, stop speculative
   edits and obtain a fresh read-only diagnosis with the reproduction, failed
   hypothesis, diff, and logs before another fix. A diagnosis may use the
   `diagnosis-review` role at the final-review tier within the same ceiling.
   An unknown cause requires more evidence, not another guess. Neither a
   diagnosis nor a replan resets the review budget.
8. Finish when the requested demo is implemented and the final reviewer approves
   the current diff under the stated prototype limitations. No job or required
   check may remain running when claiming completion.

Use extra specialists only for a specific unresolved blocking question that
the gate cannot settle from the available evidence. Main dispatches them
read-only, supplies the draft validation policy, and returns their findings
to the gate. Advisory style preferences do not start a correction cycle.

## Delivery

Keep changes local by default. Do not commit, push, open a PR, wait for CI,
update trackers, or deploy unless the user requested that lifecycle action or
an explicitly invoked outer workflow owns it. Perform requested actions only
after current final approval and within the user's validation instructions.
Any later implementation mutation invalidates approval.

The final response should say:

- what works and how to run or try the demo;
- which checks and demo steps passed, failed, or were unavailable, whether one
  existing quick test ran, and that no tests were added unless requested;
- concrete demo limitations and remaining unverified behavior;
- preflight approval or its Fast exemption, final-review decision, correction
  rounds, roles and actual models/efforts;
- local/committed/PR state and any decision still needed.

Keep reporting compact. Use token usage only when the runtime supplies it;
never invent telemetry or create accounting infrastructure for a prototype.
