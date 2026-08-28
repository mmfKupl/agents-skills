---
name: review-task
description: Explicitly invoked deep audit workflow for already implemented repository tasks, local diffs, branches, pull requests, or ticket implementations. Use when the user writes `$review-task` or asks to deeply review an implementation, verify whether a ticket was implemented correctly, find all credible risks, inspect tests, use preview/local runtime, run focused read-only validation, or create temporary probes such as Playwright checks. Invocation is an explicit request for read-only specialist delegation when useful. Do not use for implementing fixes.
---

# Review Task

## Writing quality

Before drafting the final review report, read
[`../unslop/SKILL.md`](../unslop/SKILL.md) and apply its relevant editing
guidance. Preserve user-provided wording, exact quotes, and required report
formats when they conflict with that guidance.

## Task title

Task titles are a best-effort sidebar indicator, never a workflow gate.
With a known ticket, use `<ticket-id> <description>: <status> <type>`.
Without one, use `<description>: <status> <type>`.
Write the ticket ID as plain text, never in square or round brackets.
For example: `UIB-5295 Storybook update: W review`.
When reusing a title with a bracketed ticket ID, remove those brackets.
Prefer a two-word description, with three words maximum; describe the subject
without filler such as "task", "implementation", or "scope".

Use `review` as the type when this is the active user-requested workflow.
An embedded review, worker, or validation step must not replace the outer
workflow's type or mark its task done. Only the user-facing coordinator owns
the current task's title; change type when a different requested workflow
actually starts.

Use only these statuses:

- `W` Working: progressing independently, including waiting for tests, CI, or
  agents that the workflow will handle without a user reply.
- `R` Reply needed: pausing for the user's answer, choice, or approval.
- `B` Blocked: stopped by an obstacle such as missing access or an unavailable
  dependency. Use R instead when the next step is a user decision.
- `D` Done: the requested work is complete, not simply the current turn.

For review, D means the requested audit and report are complete, not that the
implementation has no findings or is merged.
Use W again when work resumes. Recoverable errors remain W while being handled;
there is no E status. A title-tool failure never changes the work's status.

At entry, take one small `list_threads` snapshot when available. Reuse the
most recent matching description for the same explicit ticket, shortening it
to the word limit if necessary; otherwise choose from known task context.
Recognize current titles and both older `<description>: <type>` and
`<type>: <description>` formats. Keep the chosen description stable.
Best-effort align descriptions of matching tasks within the same short budget,
preserving each task's own type and existing status. Never guess another
task's status, add one to a legacy title, or rename unrelated tasks.

Update the current title with `set_thread_title` at entry and when its status
or active workflow changes, including before asking a blocking question or
sending the final result. Skip already-confirmed identical titles. A successful
tool response confirms the update; do not add a separate readback after success.

Keep this cheap: use bounded/asynchronous execution with a shared foreground
wait budget of about two seconds per checkpoint for all title tools, including
listing and readback. If unavailable, slow, or failed, continue the real work;
defer further title calls and retain only the latest desired title as pending.
Do not stack in-flight title writes. At a later natural work checkpoint, make
at most one deferred verification/retry per turn, plus one final attempt before
yielding to the user. Check any existing attempt first; if its outcome is
unknown, use a single small snapshot before retrying. Replace stale pending
states with the current one. Apart from the final attempt, leave further retries
for the next turn.
Do not repeatedly list tasks, poll, sleep, create a reminder, diagnose the app,
or ask the user for help solely to update a title. Do not claim success without
confirmation. Titles may be stale while the desktop app is offline.

These narrow Codex title updates are permitted even in read-only workflows;
they do not authorize ticket, PR, code, or other external changes.

## Core Contract

Audit one already implemented task. Find credible correctness, requirement, testing, runtime, simplicity, and repository-practice issues. `review-task` owns review orchestration, evidence collection, validation selection, and the final risk report.

Do not fix product code, update tests permanently, commit, push, edit PRs, update Linear, or manage lifecycle state. If the review finds issues, report them clearly so the user can delegate fixes to the right workflow.

Treat an explicit `$review-task` invocation as explicit user authorization to use read-only review delegation. This includes `$diff-review` and specialist agents listed below. Do not skip those agents merely because the user did not separately say "subagent", "delegate", or "parallel agents".

You may run read-only inspection commands and focused validation. Avoid persistent repository edits. If a probe needs code, prefer temporary files outside the repository, one-off command snippets, Browser/Playwright automation, or an existing test harness in dry-run form. Ask before any expensive, destructive, or externally mutating action, except for narrow repository-approved validation triggers explicitly needed to satisfy the review target's stated validation bar.

## Review Depth

Use the user's wording to choose depth:
- `standard`: default; inspect requirements, diff, repository context, delegated reviews, and focused existing checks.
- `deep`: use when the user asks for a very detailed review, mentions preview/runtime verification, or the change is risky; include runtime smoke checks and temporary probes when useful.
- `audit`: use when explicitly requested; be maximally thorough, but ask before long-running suites, environment setup, or broad CI-equivalent work.

## Specialist Model Routing

The shared review-agent TOML files intentionally do not pin a model or
reasoning effort. For every specialist agent spawned by this workflow, pass one
explicit callable model ID and effort and use `fork_turns: "none"` or a
positive bounded history with a self-contained review packet.

- `standard`: `gpt-5.6-terra` high;
- `deep`: `gpt-5.6-sol` high;
- `audit`: `gpt-5.6-sol` xhigh by default;
- use `gpt-5.6-sol` max only when several critical risks combine, failure is
  especially costly or hard to validate, or a lower Sol tier made a conceptual
  mistake.

Raise the route when repository evidence is riskier than the user's depth word.
Do not silently downgrade when a selected route is unavailable. Use an
equivalent-or-stronger available route, or perform the check manually and report
the delegation gap.

## Workflow

1. Identify the review target: local diff, branch, commits, PR, ticket, or provided patch. If ambiguous, infer the current repository diff; ask only when multiple targets are equally plausible.
2. Read repository instructions such as `AGENTS.md`, inspect `git status --short --untracked-files=all`, and avoid changing the worktree.
3. Reconstruct intent from available sources: user request, ticket, PR, commit messages, OpenSpec, code comments, and acceptance criteria. Do not invent missing business requirements; report gaps as uncertainty.
4. Map the implementation: changed files, touched subsystems, contracts, state flow, persistence, UI/runtime paths, validation surface, and likely failure modes.
5. For every potential finding, compare the failure path with the reconstructed task boundary. A credible risk may still be worth reporting when it is outside scope, but call it out as follow-up work rather than an implementation defect unless an explicit requirement or preserved contract covers it.
6. Collect existing validation evidence before running anything new.
7. Reuse fresh passed checks when they already cover the current risk. Do not rerun tests just to duplicate credible evidence.
8. If the ticket, PR, OpenSpec, or review target states a concrete validation bar, satisfy that bar when technically available.
9. Run only missing focused validation that can materially change confidence. Prefer narrow tests, type/lint checks, targeted integration tests, preview smoke checks, or temporary probes over broad suites.
10. Use supporting skills or agents when available and useful:
   - `$diff-review`: independent fresh diff pass.
   - `repo-practice-review`: repository conventions, helpers, ownership, and local patterns.
   - `best-practice-review`: general engineering risks and weak precedent challenges.
   - `test-review`: test adequacy, missing regression coverage, and e2e/smoke strategy.
   - `code-simplicity-review`: scope creep, unnecessary code, simpler approaches, helper/library reuse.
11. If supporting agents are technically unavailable, perform the same checks manually and say that delegation was not available. Do not call delegation unavailable only because the user did not repeat the delegation request outside `$review-task`.
12. Correlate all evidence yourself. Specialist output is evidence, not the final verdict.
13. Report findings first, ordered by severity. Include validation evidence and remaining gaps.

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

## Stated Validation Bars

When requirements specify a concrete validation bar, treat it as part of the implementation contract, not as an optional confidence note. Examples include `10/10 focused reruns`, `N consecutive e2e passes`, `no failures across repeated preview runs`, or a named flaky-test reproduction/fix bar.

For stated bars:
- count fresh existing passes toward the bar only when they match the same commit, test target, environment, and command intent;
- run the missing repetitions yourself when the target command, CI trigger, preview URL, or local environment is available and safe enough for review validation;
- stop early and report a confirmed finding if any required repetition fails;
- if a bar requires a repository-approved external test trigger, such as a PR comment that starts focused e2e, keep the action limited to that validation trigger and do not edit PR metadata or lifecycle state;
- if the bar cannot be executed because credentials, environment, runner access, time, or safety constraints block it, report that as a validation gap with the exact blocker and do not phrase it as merely "weaker evidence".

Do not replace a stated repeated-run bar with a single green run unless the requirement owner explicitly relaxed the bar.

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

## Report Mode

Select `standalone` only when all of the following are true:
- the end user's active request directly invokes `$review-task` or asks for the review as the deliverable;
- this agent owns the final user-facing review response;
- the review is not an internal implementation step, self-review, validation gate, or input to another agent or workflow.

Otherwise select `embedded`. Do not ask the user to choose a mode. An explicit mode requested by the user or calling workflow overrides automatic selection.

Use `standalone` for the full user-facing report. Use `embedded` for only actionable findings, validation evidence, validation gaps, delegation, and the verdict; omit the explanatory task brief.

## Output

Lead with findings:

- Severity: `P0` critical, `P1` blocking, `P2` important, `P3` minor.
- Title: short problem statement.
- Evidence: files, lines, diff context, runtime result, or test result.
- Impact: what can break and for whom.
- Reproduction or check: command, preview path, probe, or reasoning path.
- Scope assessment: a short prose explanation of whether the finding is in scope, on the boundary, or outside scope, and why.
- Suggested direction: concise fix strategy, not a full implementation plan unless asked.

Then report:
- Validation reused: passed checks accepted as evidence.
- Validation run: commands, probes, preview checks, and results.
- Validation gaps: what was not checked and why.
- Delegation: agents used or manual fallback.
- Verdict: `blocked`, `risky`, `mostly-ready`, or `no-findings`, with residual risk.

If no issues are found, say that clearly and still list reused checks, newly run checks, and remaining risk.

In `standalone` mode, append a concise `Task brief` after the verdict:
- Task: what problem or requested behavior the change addresses.
- Key points: the essential requirements, constraints, and affected behavior.
- Implemented solution: the approach the implementation ultimately takes.
- Why this solution: the documented rationale and tradeoffs. If the rationale is not documented, clearly label the explanation as an inference from the diff, requirements, and repository patterns.

Keep the brief evidence-based and avoid repeating findings or inventing missing product intent. In `embedded` mode, stop after the verdict and residual risk.
