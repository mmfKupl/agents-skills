---
name: iterable-workflow
description: Use only when the user explicitly asks to follow a staged, approval-driven, iterative development workflow. Do not use for routine tasks unless the user requests this workflow by name or clearly asks to work in their staged flow.
metadata:
  short-description: Staged iterative development flow
---

# Iterable Workflow

Use this skill only on explicit request.

## Core behavior

- Treat the task as staged work with explicit checkpoints.
- Ask at most one question at a time.
- Whenever you ask a question, include concise examples of common-practice options or defaults.
- Never run e2e tests yourself. If e2e coverage would normally be relevant, say so explicitly and propose a narrower verification path instead.

## Workflow

1. Define the task and identify missing acceptance criteria, constraints, or decision points.
2. If information is missing, ask one question only and wait for the answer before asking the next question.
3. Present a concrete task plan and wait for approval before making code changes.
4. Inspect the codebase for existing patterns and similar implementations.
5. Re-evaluate the chosen approach against what was found and confirm or adjust it before implementation.
6. Implement the production code iteratively without changing tests yet, unless the user explicitly asks otherwise or test edits are required to unblock the implementation safely.
7. Summarize the implementation changes and wait for approval before touching tests.
8. Only after approval, add or update tests.
9. Run the smallest relevant non-e2e verification and report both what was checked and what was intentionally not run.

## Question style

When asking a question:

- Ask only one question.
- Keep it short and specific.
- Include 2-4 concise examples of common-practice choices or defaults.
- If a reasonable default exists, state which default you would choose absent guidance.

## Overrides

- The user can skip, reorder, or collapse any stage.
- For trivial tasks, keep the stages brief but preserve the checkpoint order.
- If the user asks for faster execution, compress the process, but do not run e2e tests.
