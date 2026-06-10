---
name: develop-loop
description: Controlled development loop for fixing PR feedback, GitHub review comments, Linear-linked bugs, or user-provided issue lists one item at a time. Use when the user wants Codex to implement fixes incrementally with explicit approval before commit, push, or resolving review threads; especially for UI Bakery work, PR comment cleanup, regression fixes, and "fix these problems in order" workflows. Uses diff-review as a review gate for complex, risky, or disputed changes.
---

# Develop Loop

## Core Contract

Work one issue at a time. Do not commit, push, open/resolve PR threads, or move to the next issue until the user explicitly approves the current fix.

If the user provides a priority order, follow it. If not, choose a conservative order: correctness/data-loss/security first, then user-visible bugs, then API compatibility, then cleanup.

## Per-Issue Workflow

1. Restate the current issue briefly and identify the files or subsystems to inspect.
2. Study existing patterns before editing. Search for similar reducers, effects, services, tests, APIs, and call sites.
3. Confirm the issue is real. If the bug cannot be confirmed, explain the uncertainty and ask before changing behavior.
4. Implement the smallest scoped fix that matches the local code style.
5. Add or update a regression test when practical. Prefer focused tests over broad suites.
6. Run the narrowest useful verification command. If a required check cannot run locally, report the exact environment blocker and run the next-best compile/static check.
7. Check the diff for unrelated edits, accidental staging, whitespace, and noisy refactors.
8. Report the fix and stop for user approval.

## Report Format

When a fix is ready for approval, include:

- Problem: what was broken in user-facing or system terms.
- Cause: where the bug came from.
- Fix: what changed.
- Verification: commands run and their result.
- State: whether files are staged, committed, pushed, or unresolved.
- Review gate: whether `diff-review` was run, skipped, or blocked.

Use concrete examples when the user asks "what happened?", "how can I reproduce?", or challenges whether the issue is real.

## Approval Gate

Before approval, leave changes local unless the user explicitly asked otherwise. The expected resting state after implementation is:

- no commit;
- no push;
- no GitHub thread resolution;
- no transition to the next issue;
- staged changes only if the user explicitly asked for staging.

When the user approves the current fix:

1. Stage only files that belong to the approved fix.
2. Commit with the repository's commit rules.
3. Push only when requested by the user or required by the active PR workflow.
4. Resolve only the matching review thread.
5. Continue to the next issue.

## Diff Review Gate

Use `diff-review` before presenting the fix as ready when any trigger applies:

- the user questioned the problem, reproduction, or necessity of the fix;
- the fix touches public API, persistence, permissions, auth, billing, concurrency, NgRx state, effects, backend/frontend contracts, migrations, or generated-code/runtime contracts;
- the change spans more than one layer;
- the implementation introduces a helper, abstraction, or non-obvious control flow;
- a focused test cannot run in the local environment;
- the first fix feels larger than the bug;
- the user says "можно проще", "перепроверь", "я не понимаю", "сомневаюсь", or asks for a subagent/fresh review.

Skip `diff-review` for small, obvious, single-file fixes with a focused passing regression test, unless the user asks for it.

When the gate triggers, follow the `diff-review` skill if available. If it is not available, run the same workflow directly: review the current diff from a fresh perspective, look for correctness risks and simpler alternatives, apply only technically justified feedback, and re-run focused verification.

## Handling User Challenges

If the user challenges the explanation or says the scenario does not make sense:

1. Pause implementation.
2. Re-check actual call sites and reproduction paths.
3. Separate common UI behavior from lower-level API or edge-case behavior.
4. Explain whether the issue is real, not reproducible, or only relevant in a narrower scenario.
5. Use `diff-review` if the fix remains non-obvious.

## Backlog Notes

If the user mentions an additional issue while another fix is in progress, add it to the plan/backlog and keep working on the current approved order unless the user explicitly reprioritizes.
