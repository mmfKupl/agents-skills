---
name: openspec-workflow
description: Inspect, initialize, create, update, and validate local OpenSpec artifacts for repository development tasks. Use when a task explicitly asks for OpenSpec, when `develop-task` decides OpenSpec is warranted for large/complex/ambiguous/cross-layer/high-risk/durable behavior work, or when existing OpenSpec specs/changes must be consulted or kept in sync.
---

# OpenSpec Workflow

## Purpose

Use local OpenSpec artifacts to preserve behavior intent for complex repository work without making OpenSpec mandatory for small obvious changes.

OpenSpec does not replace `AGENTS.md`, repository patterns, tests, validation, or review gates. If OpenSpec conflicts with explicit user instructions, `AGENTS.md`, or code evidence, surface the conflict and follow the stronger instruction.

## When To Use

Use OpenSpec by default for:
- large, complex, ambiguous, cross-layer, high-risk, or durable behavior changes;
- tasks where implementation intent may be lost across chat context, review cycles, or follow-up sessions;
- tasks explicitly asking for OpenSpec;
- tasks already tied to an existing `openspec/changes/<change-id>/`.

Skip OpenSpec for:
- small obvious local fixes;
- mechanical refactors;
- formatting-only work;
- dependency bumps with no behavior design;
- tasks where code, tests, and commit message carry enough intent.

## Repository Layout

Prefer this local layout:

```text
openspec/
  config.yaml
  README.md
  specs/
    openspec-workflow/
      spec.md
  changes/
    <change-id>/
      proposal.md
      design.md
      tasks.md
      specs/
        <capability>/
          spec.md
```

Use `openspec/specs/` for durable behavior specs. Use `openspec/changes/<change-id>/` for proposed deltas tied to real tasks.

## Local Initialization

Before creating artifacts, check whether `openspec/` exists.

If absent and OpenSpec is warranted:
1. Prefer the OpenSpec CLI when available:
   ```bash
   openspec init --tools codex
   ```
2. If the CLI is unavailable, create the minimal layout:
   - `openspec/config.yaml`;
   - `openspec/README.md`;
   - `openspec/specs/openspec-workflow/spec.md`.
3. Add `/openspec/` to `.git/info/exclude` by default so pilot artifacts stay local.
4. Use `.gitignore` only when the user explicitly wants repository-shared ignore behavior.

Do not commit OpenSpec artifacts unless the user or repository policy explicitly wants OpenSpec tracked.

## Change Workflow

When a task uses OpenSpec:
1. Read `AGENTS.md` first.
2. Read `openspec/README.md` and `openspec/config.yaml` when present.
3. Read relevant specs under `openspec/specs/`.
4. Choose a stable `<change-id>` such as `fix-public-app-auth-isolation`.
5. Create or update `openspec/changes/<change-id>/`.
6. Write `proposal.md` with problem, goals, non-goals, and evidence.
7. Write delta specs under `specs/<capability>/spec.md` using `ADDED`, `MODIFIED`, or `REMOVED Requirements`.
8. Add `design.md` when architecture, cross-project boundaries, persistence, permissions, rollout, or runtime risk matters.
9. Add `tasks.md` with implementation, validation, rollout, and cleanup items.
10. Keep artifacts scoped to real opted-in work; do not add speculative product specs.

## Validation

When the CLI is available, use:

```bash
openspec list
openspec show <change-id>
openspec validate <change-id>
```

If the CLI is unavailable, do a structural check:
- change has `proposal.md` and `tasks.md`;
- `design.md` exists when architecture/risk warrants it;
- delta specs describe observable behavior, not implementation trivia;
- tasks include implementation and validation;
- artifacts do not contradict `AGENTS.md`, code evidence, or user instructions.

## Post-Implementation Sync

After implementation:
- update `tasks.md` checkboxes for completed work;
- document skipped validation or remaining limitations;
- check that specs still match the diff;
- do not archive changes automatically unless the user explicitly asks or repository practice requires it.

## Output

When reporting OpenSpec work, include:
- OpenSpec status: absent, initialized, existing, or updated;
- change id and artifact paths;
- validation command/result or manual validation notes;
- whether artifacts are local ignored or intended for commit;
- remaining OpenSpec tasks or drift.
