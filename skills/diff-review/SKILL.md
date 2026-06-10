---
name: diff-review
description: Independent fresh review workflow for local diffs. Use when the user asks to review a current diff, run a subagent without prior context, check whether a fix can be simpler, validate a risky or disputed implementation, or when another skill such as develop-loop needs a review gate before approval, commit, push, or resolving review threads.
---

# Diff Review

## Goal

Review the current local diff as independently as possible. Find correctness risks, missing tests, overengineering, scope creep, and simpler approaches before the change is committed or used to resolve a review thread.

## Preferred Workflow

1. Collect the current diff and the smallest necessary surrounding context.
2. Start a subagent without conversation/fork context when that tool is available.
3. Give the subagent only:
   - the diff;
   - relevant file snippets or paths;
   - the expected behavior;
   - a request to check correctness, simplicity, tests, and edge cases.
4. Do not include prior reasoning, intended solution, hidden conclusions, or user-agent debate.
5. Compare the subagent's feedback against the repository before changing code.
6. Apply only feedback that is technically justified.
7. If the implementation changes, re-run focused verification.
8. Report what the review found and what changed because of it.

## Fallback Workflow

If a subagent tool is not available, do a manual fresh pass:

1. Read the diff from top to bottom without defending the current implementation.
2. Ask whether the bug can be fixed closer to the boundary where the bad state enters.
3. Check whether a new helper or abstraction is truly needed.
4. Check whether the test proves the bug, not only the implementation.
5. Check whether stale state, race conditions, nullability, public API compatibility, or cross-layer contracts are affected.
6. Keep, simplify, or reject the current approach based on code evidence.

## Review Prompt Template

Use this shape for a subagent prompt:

```text
Review this local diff independently.

Expected behavior:
<brief behavior or bug statement>

Please look for:
- correctness bugs;
- simpler or more idiomatic implementation;
- missing regression coverage;
- over-broad behavior changes;
- edge cases.

Do not assume the current implementation is correct.

Diff:
<diff>
```

## Output

Report:

- whether an independent subagent review was run or a manual fallback was used;
- important findings;
- which suggestions were applied or rejected;
- verification rerun after changes;
- remaining risk, if any.
