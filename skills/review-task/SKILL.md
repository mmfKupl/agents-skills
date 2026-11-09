---
name: review-task
description: "Deep read-only audit of an implemented task, diff, branch, PR, or ticket: find credible risks, inspect tests, and run focused checks. Use only when the user writes `$review-task` (or `/review-task` in Claude Code) or asks for a deep review of an implementation. Not for implementing fixes."
---

# Review Task

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else, including the entry task title. It maps Codex tools, model
names, task titles, and delegation to Claude Code; every gate and rule in this
skill still applies.

## Task title

At entry, read [`../chat-title/SKILL.md`](../chat-title/SKILL.md) and follow it with
the type `review`. `D` means the requested audit and report are complete, not that the implementation
has no findings or is merged.

## Core Contract

Audit one implemented task for credible correctness, requirement, testing,
runtime, simplicity, and repository-practice issues. In standalone mode you own
orchestration, evidence collection, validation selection, and the final risk
report.

Stay read-only: do not fix product code, keep test changes, commit, push, edit
PRs, update Linear, or manage lifecycle state; report issues for the user to
delegate.

`$review-task` authorizes read-only delegation to `$diff-review` and the
specialists below; do not wait for a separate request for subagents.

Avoid persistent repository edits; probe with temporary files outside the
repository, one-off snippets, Browser/Playwright, or a harness in dry-run form.
Ask before any expensive, destructive, or externally mutating action, except a
narrow repository-approved trigger a stated validation bar needs.

## Embedded development audit

When explicitly combined with `$develop-task` for one implementation task, read
[`../develop-task/references/composed-workflows.md`](../develop-task/references/composed-workflows.md).
Main applies this audit in the shared run with develop-task's backend, matrix,
ceiling, requirements, coverage plan, and usage accounting: no standalone model
defaults, second orchestrator, or unrequested brainstorm.

The independent final postflight reviewer performs the audit from a fresh
packet with the original requirements, current diff, base revision, and
validation evidence, using supported shared roles rather than a separate
diff-review backend. Develop-task's authorized writer owns
fixes and its gate owns approval. Main triages findings under the shared
correction budget; the audit has no fix loop or completion/lifecycle authority.

## Review Depth

Choose from the user's wording:
- `standard` (default): the workflow below with focused existing checks.
- `deep`: on request for a very detailed review or runtime/preview checks, or for risky changes; add runtime smoke checks and temporary probes when useful.
- `audit`: only on explicit request; be maximally thorough, but ask before long-running suites, environment setup, or broad CI-equivalent work.

## Specialist Model Routing

These defaults apply only to standalone review. Give every specialist an
explicit callable model ID and effort, and `fork_turns: "none"` or a positive
bounded history with a self-contained packet.

- `standard`: `gpt-6.1-terra` high; `deep`: `gpt-6.1-sol` high; `audit`:
  `gpt-6.1-sol` xhigh by default.
- `gpt-6.1-sol` max only when several critical risks combine, failure is
  especially costly or hard to validate, or a lower Sol tier made a conceptual
  mistake.
- Runtime, preview, and visual probes (rendered UI, screenshots, Playwright)
  use `gpt-6.1-terra` high at any depth; the depth's model judges defects.

Raise the route when repository evidence is riskier than the depth word. If a
route is unavailable, use an equivalent-or-stronger one or check manually and
report the delegation gap; never silently downgrade.

## Workflow

1. Identify the target: local diff, branch, commits, PR, ticket, or patch. Default to the current diff; ask only when several targets are equally plausible.
2. Read repository instructions such as `AGENTS.md` and `git status --short --untracked-files=all`.
3. Reconstruct intent from the request, ticket, PR, commits, OpenSpec, and acceptance criteria. Report missing business requirements as uncertainty; do not invent them.
4. Map changed files, subsystems, contracts, state flow, persistence, runtime paths, and likely failure modes.
5. Collect existing validation evidence first. Run only missing focused validation that can change confidence, preferring narrow checks or temporary probes over broad suites.
6. Delegate when useful: `$diff-review` (fresh diff pass), `repo-practice-review` (local conventions and helpers), `best-practice-review` (engineering risks, weak precedent), `test-review` (coverage and e2e/smoke strategy), `code-simplicity-review` (scope creep, simpler approaches). If agents are technically unavailable, do their checks manually and say so.
7. Correlate all evidence yourself; specialist output is evidence, not the verdict.

## Coverage and baseline verification

Check coverage of the requested behavior across relevant layers, not only the
tests and files the implementation chose; trace new supported variants into
story and fixture matrices, permission tests, and runtime flows. A green suite
or approved scope does not prove an omitted scenario. Report a missing artifact
only when the requested behavior or demonstrated repository practice requires
it.

Compare each credible finding with the base revision when available. Tie scope
to a requirement or preserved contract, not severity or file proximity. A
pre-existing issue that stops a requirement from holding is not automatically
out of scope; other out-of-scope risks are follow-up work, not defects or a
reason to broaden the patch. If origin or required behavior is unclear, report
the uncertainty instead of guessing or proposing new product behavior.

## Passed Check Reuse

Cite a passed test, CI job, or command instead of rerunning it when it ran on
the same commit, head, or diff after the relevant changes; its exact name and
result are known; its scope covers the touched code or risk; and no relevant
dependency, environment, configuration, or generated artifact changed since.

Rerun or supplement when it is stale, failed, flaky, skipped, cancelled, or of
unknown scope; ran on the base, an older commit, or before relevant changes;
does not cover the risk under review or a new review hypothesis; or the user
asks.

## Stated Validation Bars

A concrete bar in the requirements or target, such as `10/10 focused reruns`,
is part of the contract. Meet it when technically available.

- Count existing passes only when they match the commit, test target, environment, and command intent; run missing repetitions when safe.
- Stop and report a confirmed finding on any failed repetition.
- For a repository-approved external trigger, such as a PR comment starting focused e2e, do only that; do not edit PR metadata or lifecycle state.
- If credentials, environment, runner access, time, or safety block the bar, report a validation gap naming the blocker, not "weaker evidence".
- One green run never replaces a repeated-run bar unless the requirement owner relaxed it.

## Runtime And Preview Verification

With a preview URL, deployed build, or running local environment, safely test
high-risk UI/runtime behavior. UI: Browser/Playwright smoke checks of concrete
flows (visible state, network/runtime errors, navigation, loading/empty/error
states, responsive behavior when relevant); temporary probes only when they add
evidence beyond manual inspection or existing e2e. Backend: focused API,
service, migration, or integration checks via repository commands. Mutate
production-like data only where explicitly safe for testing.

## Review Checklist

Look for happy-path-only behavior; missing null, empty, permission,
concurrency, retry, pagination, timezone, migration, rollback, or compatibility
handling; stale state, lifecycle, cache, event, subscription, or async races;
data loss, persistence drift, schema mismatch, or unsafe migrations; UI
workflow gaps, broken loading/error/empty states, inaccessible controls, or
layout regressions; and security, authorization, tenant isolation, secret exposure,
or unsafe external calls.

Also check, yourself when no specialist covers it: mismatch with stated requirements or
acceptance criteria; tests that overfit the implementation, miss the actual regression,
duplicate coverage, or are brittle; unnecessary abstractions, scope expansion, dead code,
or custom logic where repository helpers or libraries exist; and deviation from
repository practice without a justified reason.

## Evidence Standards

Be strict, not noisy: a finding needs a plausible failure path and concrete
evidence from code, requirements, tests, runtime, or a reproducible check.
Separate confirmed findings, credible risks needing owner judgment, validation
gaps, and open requirements questions. Do not bury important issues in a long
summary or present style opinions as blocking defects.

## Report Mode

Use `standalone` only when the end user's active request directly invokes
`$review-task` or asks for this review as the deliverable and you own the final
response; an implementation step,
self-review, gate, or input to another agent or workflow is `embedded`. An
explicit mode from the user or calling workflow wins; never ask. `embedded`
reports only actionable findings, validation evidence and gaps, delegation,
and the verdict.

## Output

Findings first, by severity. Each gives Severity (`P0` critical, `P1`
blocking, `P2` important, `P3` minor), Title, Evidence (files, lines, or
check results), Impact (what breaks, for whom), Reproduction
or check (command, preview path, probe, or reasoning), Origin (introduced,
pre-existing and exposed, unrelated pre-existing, or unknown, with baseline
evidence), Scope assessment (in scope, boundary, or outside, and why), and
Suggested direction (concise fix strategy, not a full plan unless asked).

Then: Validation reused, Validation run (with results), Validation gaps (what
was not checked and why), Delegation (agents used or manual fallback), and
Verdict (`blocked`,
`risky`, `mostly-ready`, or `no-findings`, with residual risk). With no
findings, say so and still list the checks and remaining risk.

In `standalone` mode, append a concise, evidence-based `Task brief` after the
verdict: Task, Key points (essential
requirements, constraints, affected behavior), Implemented solution, and Why
this solution (documented rationale and tradeoffs; label anything undocumented
as an inference from the diff, requirements, and repository patterns). Do not
repeat findings or invent product intent.
