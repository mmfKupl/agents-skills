---
name: develop-task
description: Orchestrated development workflow for implementing code tasks with explicit preflight and postflight custom-agent review gates. Use when the user asks Codex to fix a bug, implement a feature, address PR feedback, or work through a task carefully while keeping commits, pushes, and review-thread resolution behind explicit approval. Uses the preflight-review custom agent before edits and the postflight-review custom agent after implementation, with a default 3-cycle review limit.
---

# Develop Task

## Core Contract

Implement one coherent task at a time. Keep the main agent responsible for all file edits. `preflight-review` and `postflight-review` are read-only custom agents: they inspect, critique, and return briefs/findings; they do not edit files, commit, push, or resolve review threads.

Unless the user explicitly asks otherwise, stop after implementation and verification with local changes uncommitted. Do not commit, push, open or resolve PR threads, change Linear, or move to another task without explicit user approval.

Default postflight fix loop limit: 3 cycles. If blocking findings remain after 3 postflight cycles, stop and ask the user how to resolve the conflict.

## Workflow

1. Understand the request and identify the current task boundary. If the user provides a list, work only on the current item.
2. Read `AGENTS.md` and inspect `git status --short --untracked-files=all`.
3. Stop and ask before carrying unrelated staged or unstaged user changes into the task.
4. Gather minimal context: owner, likely files, nearby patterns, existing tests, and reproduction path when relevant.
5. Draft a short initial approach in working context.
6. Spawn or invoke the `preflight-review` custom agent before editing. Pass the user request, initial approach, likely files or subsystems, relevant constraints, dirty-tree notes, and expected behavior.
7. Wait for the preflight brief. Resolve blockers before editing. If the brief changes the approach, follow the corrected owner, boundary, and validation plan unless repository evidence contradicts it.
8. Implement the smallest scoped fix that matches local patterns.
9. Add or update behavior-focused tests when risk and coverage justify it.
10. Run focused validation from the correct working directory. Broaden only when touched shared behavior needs it or focused checks cannot cover the risk.
11. Spawn or invoke the `postflight-review` custom agent on the resulting diff. Pass the diff summary, changed files, tests run, skipped checks, and any known limitations.
12. Relay the postflight result in the main chat before changing code again. Do not rely on the subagent UI/card as the only visible record.
13. Apply blocking postflight findings, rerun focused verification, and repeat postflight review. Count each postflight review after implementation as one cycle.
14. After approval from `postflight-review`, or after stopping on a 3-cycle unresolved review loop, report the result to the user.

## When To Use The Review Agents

Use `preflight-review` and `postflight-review` by default for non-trivial tasks, PR feedback, unclear bugs, public API or contract changes, cross-layer work, state/runtime changes, persistence, permissions, auth, billing, migrations, data-source execution, generated-code/runtime behavior, and any task where the first implementation could plausibly be improved by an independent architecture pass.

For tiny, obvious, single-file edits with no behavior risk, a focused passing check, and no user request for a careful flow, you may skip custom-agent review. Say that it was skipped and why.

Always use the review agents when the user says "перепроверь", "можно лучше", "я не понимаю", "сомневаюсь", asks for an architect/reviewer/subagent, or explicitly invokes `$develop-task`.

If custom agents are unavailable in the current Codex surface, run the same preflight/postflight checks manually and clearly report the fallback.

## UI Bakery Owner Map

Use this as a starting point, then verify with code:

- Custom Apps AI agent runtime: `front/projects/chat/app/agent`
- Custom App renderer/runtime: `front/projects/components/src/lib/custom-react-app`
- AI builder UI in Bakery: `front/projects/bakery/src/app/tools/builder/module-chat`
- User-facing bottom-tab assistant, unrelated to Custom Apps: `front/projects/bakery/src/app/tools/layout/bottom-tabs/chat-dialog`
- Bakery Angular shell and workspace/account UI: `front/projects/bakery`
- Workbench builder canvas and preview host: `front/projects/workbench`
- Oven renderer library: `front/projects/oven`
- Low-code component definitions and schemas: `front/projects/components`
- Datasource runtime and connectors: `front/projects/datasource`
- Automations frontend/server: `front/projects/automation`
- Chat backend service: `front/projects/chat`
- Docker sandbox service: `front/projects/docker-sandbox`
- Java backend: `back/projects/bakery` and `back/projects/bakery-cloud`

## Validation Hints

Choose the narrowest check that proves the behavior:

- Angular project changes: affected `front` test target, focused lint/typecheck when available.
- Chat backend or Custom Apps agent changes: focused Jest tests in `front/projects/chat`, plus evals for generated-app, tool, planning, datasource sync, screenshot, file operation, or sandbox behavior changes.
- Datasource changes: `front/projects/datasource` tests.
- Docker sandbox changes: `front/projects/docker-sandbox` tests.
- Java backend changes: narrow Maven test from `back/projects` or compile check when Testcontainers/Docker blocks integration tests.
- Duplication-sensitive broad frontend changes: `cd front && npm run jscpd`.
- User-visible UI changes: consider screenshot or Browser/Playwright smoke when runtime layout matters.

Do not run known expensive commands such as `npm run -s build bakery` unless the user explicitly asks or there is no smaller useful validation.

## Postflight Loop

Classify postflight feedback:

- Blocking: must fix before presenting as ready.
- Recommended: fix when it improves correctness, reduces risk, or simplifies the implementation without expanding scope.
- Optional: mention only if useful; do not churn the patch for optional opinions.

After every `postflight-review` response, paste a compact structured relay into the main chat, even if the custom-agent UI is hidden, blank, collapsed, or only shows an activity marker. Include enough detail for the user to understand the review without opening the subagent transcript:

- Blocking: concrete findings that must be fixed, or "none".
- Recommended: useful fixes accepted or declined with a short reason, or "none".
- Optional: notable opinions only when relevant, or "none".
- Validation gaps: skipped, failed, or unavailable checks, or "none".
- Approval: whether `postflight-review` approved the diff and which review cycle this was.

After each blocking fix, rerun the relevant focused checks before asking for another postflight review.

Stop after 3 postflight cycles if blocking findings remain, and report:

- current implementation state;
- remaining disputed findings;
- checks run;
- why the loop did not converge;
- the decision needed from the user.

## Report Format

When done, report:

- Problem: what was broken or requested.
- Cause: why the issue existed, when applicable.
- Fix: what changed.
- Validation: commands/checks run and results; skipped checks with reasons.
- Review gates: preflight result, postflight result, and number of review cycles.
- State: staged/uncommitted/committed/pushed status and whether approval is needed.

Keep the final response concise. Use concrete reproduction examples when the user asks for explanation or challenges the bug.
