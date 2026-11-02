---
name: trim-diff
description: Shrink an existing diff without changing its behavior. A fresh read-only reviewer traces every added hunk and test to a requirement or concrete evidence, and the unjustified parts are deleted, merged, or replaced with existing helpers. Use for $trim-diff, /trim-diff in Claude Code, or when the user asks to remove junk, overengineering, extra tests, or bloat from the current changes, a branch, or a PR.
---

# Trim Diff

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else. It maps Codex tools, model names, and delegation to Claude
Code. Only its spawning and model-map sections apply here.

## Goal

Make the diff smaller while keeping what it does. This skill only removes code:
it never adds behavior, guards, tests, or validation, and it does not review
correctness. Use `diff-review` or `review-task` for that.

`develop-task` runs the same step as its mandatory Reduction Pass. Use this
skill for work outside that workflow.

## Workflow

1. Find the diff. Default to the uncommitted changes plus commits on the
   current branch since it left the base branch. Use the branch or PR the user
   names instead. Preserve unrelated dirty files.
2. Collect the requirements: the user's request, the ticket, the PR
   description, or the commit messages. Number them. If none exist, use the
   stated purpose of the change and say so in the report.
3. Dispatch a fresh read-only `code-simplicity-review` agent with no
   conversation history. Give it only the requirements, the base revision, the
   full diff, and the paths of related existing tests. Do not give it the
   reasoning behind the implementation. Use a capable model (Terra/`sonnet` or
   higher). If the role is unavailable, run its checklist yourself and say so.
4. Check each cut against the code before applying it. Apply the ones that are
   behavior-preserving. Skip a cut when the code shows it would change required
   behavior or break a check, and record why.
5. Never apply a requirement-changing cut. List it for the user.
6. Rerun the checks that cover the changed files: the affected tests, lint, and
   typecheck. If a cut breaks a check, revert that cut rather than fixing
   forward.
7. Do not commit, push, or update a PR unless the user asked for it.

## Output

Report:

- what was reviewed: base, diff, and the requirements used;
- cuts applied, with production and test lines removed;
- cuts skipped, with the reason for each;
- requirement-changing cuts left for the user, if any;
- checks rerun and their results.
