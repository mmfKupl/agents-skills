---
name: develop-task
description: Explicitly invoked engineering workflow for repository implementation tasks with OpenSpec support, preflight/postflight review gates, specialist delegation, focused validation, logical commits, and draft PR creation. Use only when the user explicitly writes `$develop-task` or explicitly asks to run the develop-task workflow; otherwise do not select this skill.
---

# Develop Task

## Core Contract

Implement one coherent repository task at a time. `develop-task` owns phase orchestration and product-code edits. Core review gates own review decisions. Specialist agents provide narrow evidence. `openspec-steward` owns OpenSpec artifact work when OpenSpec is used.

If the active user request is analysis-only, such as asking to think through an approach, assess options, explain code, review feasibility, or propose a plan, do not make file edits, run mutating commands, spawn review agents, or start implementation. Answer with analysis only and ask for explicit approval before side effects.

Do not own business-requirements discovery. If behavior, acceptance criteria, or product intent is unclear enough that implementation would invent business behavior, stop and report that requirements discovery is needed.

Default postflight fix loop limit: 3 cycles. Default core-gate challenge loop limit: 5 iterations per disputed gate decision. If either loop does not converge, stop and ask the user for a decision.

For standalone implementation work in a git repository, the normal final state is logical commits and a draft PR unless the user explicitly asks to keep the work local. When embedded under another explicitly invoked workflow, defer lifecycle ownership to that outer workflow.

## Roles

### develop-task

Do:
- identify task boundary and repository state;
- read repository instructions;
- coordinate OpenSpec for complex work;
- invoke core gates;
- technically spawn requested specialists when a core gate cannot do nested delegation;
- edit product code and tests;
- run validation;
- make logical commits and create or update a draft PR when standalone work is approved.

Do not:
- invent business requirements;
- silently override core-gate decisions;
- interpret specialist output as the final review decision;
- encode detailed specialist routing directly in this skill;
- commit, push, or open a PR for blocked work unless the user explicitly decides to proceed.

### Core gates

Use `preflight-review` before implementation and `postflight-review` after implementation. They are read-only review controllers. They may request specialist delegation and must resolve specialist conflicts.

Use `openspec-steward` as a core-level OpenSpec agent. It may be read-only when called by a core gate for inspection or drift checks. It may write OpenSpec artifacts only when this workflow has established that the task uses OpenSpec or the user explicitly requested OpenSpec changes.

### Generalist specialists

Core gates may ask for:
- `repo-practice-review`: repository patterns, ownership, helpers, naming, local conventions.
- `best-practice-review`: general engineering practice and when to challenge weak repository precedent.
- `test-review`: focused test strategy, validation depth, test simplicity, and frontend e2e/smoke needs.
- `code-simplicity-review`: scope control, unnecessary code, simpler approaches, helper/library reuse, and quality tools.

Generalist specialists are read-only and must not recursively delegate to other agents.

## Integration Rules

When the user invokes `develop-task` together with another workflow skill, treat the other workflow as the outer controller unless the user says otherwise.

For `$develop-please`, the outer controller owns UI Bakery lifecycle behavior: Linear issue handling, branch source/base/name policy, PR target/title/body/draft-or-ready state, GitHub checks, Hetzner preview/e2e, review-thread handling, terminal Ready/No-op/Blocked outcome, and final reporting channel.

In embedded mode, `develop-task` is the engineering gate layer:
- run or request preflight and postflight review gates;
- coordinate specialist reasoning and return evidence through the requesting core gate;
- use `openspec-steward` read-only, or read-write only when OpenSpec is warranted or explicitly delegated;
- advise on task boundary, implementation risk, validation, logical change slices, and scope control;
- report gate conclusions back to the outer workflow without independently reinterpreting lifecycle rules.

Do not commit, push, open or edit a PR, update Linear, wait on CI or preview environments, or resolve review threads in embedded mode unless the outer workflow explicitly delegates that exact action.

If `develop-task` guidance conflicts with the outer workflow's lifecycle rules, follow the outer workflow and treat the gate result as engineering evidence. Explicit combined prompts such as "use `develop-task` and `develop-please`" are permission to use `develop-task` review delegation even if the outer workflow normally limits subagent use.

## Workflow

1. Understand the request and identify one current task. If the user provides a list, work only on the current item.
2. If the request is analysis-only, answer without side effects.
3. Read `AGENTS.md` and inspect `git status --short --untracked-files=all`.
4. Stop and ask before carrying unrelated staged or unstaged user changes into the task. Ignore unrelated changes when safe.
5. Gather minimal context: likely owner, files, nearby patterns, tests, reproduction path, and current branch.
6. Decide whether OpenSpec is warranted. Use OpenSpec by default for large, complex, ambiguous, cross-layer, high-risk, or durable behavior changes. Skip it for small obvious local work where code, tests, and commit message are enough.
7. If OpenSpec is warranted, invoke `openspec-steward` or use `$openspec-workflow` to inspect or create local OpenSpec artifacts before implementation.
8. Invoke `preflight-review` with the user request, task boundary, dirty-tree notes, OpenSpec status, likely files/subsystems, constraints, expected behavior, and initial technical hypothesis.
9. If `preflight-review` requests specialists, spawn them only as requested and pass the request without changing its substance. Return their results to `preflight-review` for the updated decision.
10. If you disagree with a core-gate decision, challenge it with concrete evidence. The same gate owns the updated decision. Stop after 5 unresolved challenge iterations.
11. Implement only after `preflight-review` returns `proceed` or the user explicitly decides to proceed.
12. Keep edits within the task boundary. If implementation reveals new business ambiguity or requires a materially different approach, return to preflight or stop for the user.
13. Add or update behavior-focused tests when justified. Avoid tests for everything; keep tests simple and proportional.
14. Run focused validation from the correct working directory. Broaden only when touched shared behavior needs it or focused checks cannot cover the risk.
15. Invoke `postflight-review` with the original request, preflight decision, changed files, diff, tests run, skipped checks, known limitations, OpenSpec status, review cycle number, and previous postflight findings/fixes.
16. If `postflight-review` requests specialists, spawn them only as requested and return their results to `postflight-review` for the updated decision.
17. Relay postflight findings in the main chat before changing code again.
18. Apply blocking findings, rerun focused validation, and repeat postflight review. Stop after 3 unresolved postflight cycles unless the user directs otherwise.
19. After approval, create logical commits and a draft PR for standalone repository work unless the user asked to keep changes local. In embedded mode, return approval, validation, and change-slice guidance to the outer workflow unless it delegated finalization.
20. Report the final state.

## Delegation Rules

Core gates own specialist routing. `develop-task` may technically spawn a requested specialist when nested spawning is unavailable, but must not become the reviewer/router.

For each specialist request, preserve:
- requested agent;
- blocking vs advisory status;
- mode or phase;
- exact task/question;
- required artifacts such as paths, diff snippets, OpenSpec change id, validation logs, or prior findings.

Do not expand, narrow, rewrite, or independently adjudicate the specialist request. Return specialist results to the requesting core gate. Act only on the core gate's final recommendation.

When specialist outputs conflict, the requesting core gate must explicitly decide whether to follow repository practice, depart from it, take a transitional local fix, or stop for user input.

## OpenSpec Policy

Use OpenSpec by default for:
- large, complex, ambiguous, cross-layer, high-risk, or durable behavior changes;
- tasks where intent may be lost across chat context, review cycles, or follow-up sessions;
- tasks explicitly asking for OpenSpec.

Skip OpenSpec for small, obvious, local changes where code, tests, and commit message carry enough intent.

When initializing local OpenSpec, prefer adding `/openspec/` to `.git/info/exclude` so pilot artifacts stay local unless the user explicitly wants repository-tracked OpenSpec.

`openspec-steward` may edit only OpenSpec artifacts and local git exclude files. It must not edit product code or normal tests.

## Commit And PR Policy

This policy applies to standalone `develop-task` runs. In embedded mode, return gate and validation results to the outer workflow; commit, push, or PR work only when that workflow explicitly delegates the exact action.

For standalone implementation work in a git repository, normally finish with a branch, logical commits, push, and draft PR.

Before committing:
- ensure implementation is complete;
- run focused validation or document skipped checks;
- obtain `postflight-review` approval, or get the user's explicit decision to proceed despite findings;
- ensure dirty-tree conflicts do not make task isolation unsafe.

When committing:
- split changes into logical commits instead of one broad commit;
- keep commits independently understandable and reviewable;
- avoid mixing OpenSpec/setup artifacts, product implementation, tests, and mechanical cleanup when they can be cleanly separated;
- follow configured Codex commit-message rules.

When opening the PR:
- create a branch with the configured Codex branch prefix when needed;
- push the branch;
- open a draft PR by default unless the user asks for a ready PR;
- include problem, fix summary, validation, review-gate results, OpenSpec reference when relevant, and known limitations.

Do not create a PR when:
- the request is analysis-only;
- no repository files changed;
- the task is blocked;
- postflight has unresolved blocking findings and the user did not decide to proceed;
- dirty-tree conflicts make it unsafe to isolate the task changes;
- the user asks to keep work local.

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

Each postflight call after the first must receive the cycle number and prior findings/fixes so it does not repeat optional feedback or lose track of unresolved blocking issues.

## Report Format

When done, report:

- Problem: what was broken or requested.
- Cause: why the issue existed, when applicable.
- Fix: what changed.
- Validation: commands/checks run and results; skipped checks with reasons.
- Review gates: preflight result, postflight result, and number of review cycles.
- PR: URL and draft/ready state when created, or why no PR was created.
- State: branch, staged/uncommitted/committed/pushed status and whether approval is needed.

Keep the final response concise. Use concrete reproduction examples when the user asks for explanation or challenges the bug.
