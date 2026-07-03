---
name: review-task
description: Explicitly invoked deep audit workflow for already implemented repository tasks, local diffs, branches, pull requests, or ticket implementations. Use when the user writes `$review-task` or asks to deeply review an implementation, verify whether a ticket was implemented correctly, find all credible risks, inspect tests, use preview/local runtime, run focused read-only validation, or create temporary probes such as Playwright checks. Invocation is an explicit request for read-only specialist delegation when useful. Do not use for implementing fixes.
---

# Review Task

## Core Contract

Audit one already implemented task. Find credible correctness, requirement, testing, runtime, simplicity, and repository-practice issues. `review-task` owns review orchestration, evidence collection, validation selection, and the final risk report.

Do not fix product code, update tests permanently, commit, push, edit PRs, update Linear, or manage lifecycle state. If the review finds issues, report them clearly so the user can delegate fixes to the right workflow.

Treat an explicit `$review-task` invocation as explicit user authorization to use read-only review delegation. This includes `$diff-review` and specialist agents listed below. Do not skip those agents merely because the user did not separately say "subagent", "delegate", or "parallel agents".

You may run read-only inspection commands and focused validation. Avoid persistent repository edits. If a probe needs code, prefer temporary files outside the repository, one-off command snippets, Browser/Playwright automation, or an existing test harness in dry-run form. Ask before any expensive, destructive, or externally mutating action.

## Review Depth

Use the user's wording to choose depth:
- `standard`: default; inspect requirements, diff, repository context, delegated reviews, and focused existing checks.
- `deep`: use when the user asks for a very detailed review, mentions preview/runtime verification, or the change is risky; include runtime smoke checks and temporary probes when useful.
- `audit`: use when explicitly requested; be maximally thorough, but ask before long-running suites, environment setup, or broad CI-equivalent work.

## Workflow

1. Identify the review target: local diff, branch, commits, PR, ticket, or provided patch. If ambiguous, infer the current repository diff; ask only when multiple targets are equally plausible.
2. Read repository instructions such as `AGENTS.md`, inspect `git status --short --untracked-files=all`, and avoid changing the worktree.
3. Reconstruct intent from available sources: user request, ticket, PR, commit messages, OpenSpec, code comments, and acceptance criteria. Do not invent missing business requirements; report gaps as uncertainty.
4. Map the implementation: changed files, touched subsystems, contracts, state flow, persistence, UI/runtime paths, validation surface, and likely failure modes.
5. Collect existing validation evidence before running anything new.
6. Reuse fresh passed checks when they already cover the current risk. Do not rerun tests just to duplicate credible evidence.
7. Run only missing focused validation that can materially change confidence. Prefer narrow tests, type/lint checks, targeted integration tests, preview smoke checks, or temporary probes over broad suites.
8. Use supporting skills or agents when available and useful:
   - `$diff-review`: independent fresh diff pass.
   - `repo-practice-review`: repository conventions, helpers, ownership, and local patterns.
   - `best-practice-review`: general engineering risks and weak precedent challenges.
   - `test-review`: test adequacy, missing regression coverage, and e2e/smoke strategy.
   - `code-simplicity-review`: scope creep, unnecessary code, simpler approaches, helper/library reuse.
   - `openspec-steward`: read-only OpenSpec drift or requirement artifact check.
9. If supporting agents are technically unavailable, perform the same checks manually and say that delegation was not available. Do not call delegation unavailable only because the user did not repeat the delegation request outside `$review-task`.
10. Correlate all evidence yourself. Specialist output is evidence, not the final verdict.
11. Report findings first, ordered by severity. Include validation evidence and remaining gaps.

## Passed Check Reuse

Treat an already-passed test, CI job, or validation command as usable evidence when:
- it ran against the same commit, branch head, PR head, or diff under review;
- it ran after the relevant implementation changes;
- the exact command, CI job, or check name and pass result are known;
- its scope covers the touched code or risk being assessed;
- no relevant dependency, environment, configuration, or generated artifact changed afterward.

Do not rerun such checks by default. Cite them as reused validation.

Rerun or supplement validation when:
- the check is stale, failed, flaky, skipped, cancelled, or its scope is unknown;
- it ran on the base branch, an older commit, or before relevant changes;
- it does not cover the behavior, subsystem, browser path, migration, permission boundary, or integration risk under review;
- the review introduced a new hypothesis that the existing check cannot prove;
- the user explicitly asks to rerun it.

## Runtime And Preview Verification

When a preview URL, deployed build, or already-running local environment is available, use it for high-risk UI/runtime behavior if it can be tested safely.

For UI changes:
- prefer Browser/Playwright smoke checks for concrete user flows;
- inspect visible state, network/runtime errors, navigation, loading/empty/error states, and responsive behavior when relevant;
- write temporary Playwright probes only when they add evidence beyond manual inspection or existing e2e tests.

For backend or integration changes:
- prefer focused API, service, migration, or integration checks using repository-supported commands;
- avoid mutating production-like data unless the environment is explicitly safe for testing.

If setup is missing or too expensive, report what could not be verified and why.

## Review Checklist

Check for:
- mismatch with stated requirements or acceptance criteria;
- behavior that works only for the happy path;
- missing null, empty, permission, concurrency, retry, pagination, timezone, migration, rollback, or compatibility handling;
- stale state, lifecycle, cache, event, subscription, or async race issues;
- data loss, persistence drift, schema mismatch, or unsafe migration assumptions;
- UI workflow gaps, broken loading/error/empty states, inaccessible controls, or layout regressions;
- security, authorization, tenant isolation, secret exposure, or unsafe external calls;
- tests that overfit implementation, miss the actual regression, duplicate coverage, or are too brittle;
- unnecessary abstractions, scope expansion, dead code, custom logic where repo helpers or libraries exist;
- deviation from repository practice without a justified reason.

## Evidence Standards

Be strict, not noisy. A finding must have a plausible failure path and concrete evidence from code, requirements, tests, runtime behavior, or a reproducible check.

Separate:
- confirmed findings;
- credible risks that need owner judgment;
- validation gaps;
- open requirements questions.

Do not bury important issues in a long summary. Do not present optional style opinions as blocking defects.

## Output

Lead with findings:

- Severity: `P0` critical, `P1` blocking, `P2` important, `P3` minor.
- Title: short problem statement.
- Evidence: files, lines, diff context, runtime result, or test result.
- Impact: what can break and for whom.
- Reproduction or check: command, preview path, probe, or reasoning path.
- Suggested direction: concise fix strategy, not a full implementation plan unless asked.

Then report:
- Validation reused: passed checks accepted as evidence.
- Validation run: commands, probes, preview checks, and results.
- Validation gaps: what was not checked and why.
- Delegation: agents used or manual fallback.
- Verdict: `blocked`, `risky`, `mostly-ready`, or `no-findings`, with residual risk.

If no issues are found, say that clearly and still list reused checks, newly run checks, and remaining risk.
