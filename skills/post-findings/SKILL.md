---
name: post-findings
description: "Post what a review asks the author to do, its findings and its simpler code and tests, as one comment on the ticket or the pull request: each title and why it matters stay visible, the rest is folded. Use only when the user writes `$post-findings` (or `/post-findings` in Claude Code) or asks to post the findings of a review."
---

# Post Findings

A review report is written for the developer who asked for it. The author of the change
needs less: what to fix, why, and where to read the proof. This skill posts only that,
as one comment that can be read in half a minute and opened where more is needed.

The command is the developer's permission to post this one comment. It permits nothing
else: no status change, no assignee change, no edit of the pull request.

## What to post from

Take the report in this order and say which one you took:

1. the report or the file the developer names;
2. the last review report in this chat;
3. in a project chat, the last review report of the ticket the developer names:
   `agent-projects board <project> <ticket>` prints its path.

Read the whole report. If there is none, say so and post nothing. Run no review of
your own and add no finding the report does not have.

## What goes in

- Every finding of `Findings`, in the report's order, the highest priority first.
- Every item of `Simpler code and tests`, code first, then tests.
- When the developer names some of them ("only P1", "without the tests"), only those.

Nothing else goes in: not what the change does, the verdict, `Needs from you`, the
checks, `Details`, or `Suggestions`. Those are for the developer, not for the author.

When the report has no finding and no item, say so and post nothing, unless the
developer asks for a comment that says the review found nothing.

Keep the meaning of every item as the report has it: do not soften a priority, merge
two findings, or drop a part of the proof. You may shorten the wording.

## Where to post

- The place the developer names wins: the ticket, the pull request, or a link.
- Otherwise the ticket in the tracker, when the review has one. The team reads the
  ticket, and a project chat watches its comments.
- With no ticket, the pull request, as one comment on the pull request and not as a
  review: a review would approve or block, and that is the developer's decision.
- When the repository's notes name another place for review comments, use it.

When neither a ticket nor a pull request is known, ask where to post.

Before posting, read the comments that are already there. When a comment of this
skill for the same commit exists, replace its text with the new one instead of adding
a second. A comment for an older commit stays as it is.

## The comment

Write it in the language the developer writes in this chat, unless they name another;
the labels below are translated with it. Code, names, file paths, and quoted output
stay as they are.

For a change in the UI Bakery repository, write it in English, on the ticket and on
the pull request, whatever language the developer writes in: the team reads it there.
Read the repository's `.codex/skills/linear-issue-writing/SKILL.md` first and follow
its rules for comments; the format below already leads with the result. When this
checkout is older than that file, read it with `git fetch origin dev` and
`git show origin/dev:.codex/skills/linear-issue-writing/SKILL.md`.

What is visible without opening anything: the first line, and for each finding its
title and why it matters. Everything else of a finding is folded under it. Simpler
code and tests is one fold as a whole: the author opens it after the findings.

```markdown
**Review of <the pull request as a link, or the change> · commit `<short hash>` · findings: <count>, simpler: <count>**

### Findings

**<P0 | P1 | P2 | P3> — <the finding's title, as in the report>**
<Why it matters: who is affected and how badly, in one or two sentences>

<fold "Details">
- **What happens** — <as in the report>
- **Where and since when** — <file and line as a link, and whether the change brought it>
- **How it was confirmed** — <the check and its result>
- **Fix direction** — <as in the report>
</fold>

<fold "Simpler code and tests: <count>">
**<Code | Tests> — <what to do, in one line: delete, merge, inline, replace with which helper, add which test>**
<What it gives: about how many lines go, or which behavior a test starts to prove>
<file and line as a link, and the rest of the item>

<the next item, the same way>
</fold>
```

Rules for it:

- Leave out the Findings heading or the fold of Simpler code and tests when it has
  nothing, and its count in the first line.
- Simpler code and tests has no heading of its own: the title of its fold is the
  heading. Every item is inside that one fold, with no fold of its own.
- A title says what goes wrong or what to do in plain words. When the report's title
  is longer than one line, shorten it and keep the full one first under the fold.
- Put an empty line between items, and no rule between them.
- A file and line is a link to that line at the reviewed commit when the repository's
  address is known, so that it still points at the same code after new commits.
- Add no greeting, no summary of the pull request, no praise, and no sign-off.

How a fold is written depends on where the comment goes:

| Place | A fold |
|---|---|
| Linear | a line `+++ <title>`, the text, then a line `+++` |
| GitHub | `<details><summary><title></summary>`, an empty line, the text, an empty line, `</details>` |
| Any other place | no fold: the title in bold, then the text |

Before posting, read the comment once as the author would, without the report: each
finding's title with its two lines must say what is wrong and why it matters without
the fold being opened.

## Posting

Post with the tool the chat has for that place: the tracker's own tool for a ticket,
`gh pr comment --body-file` for a pull request. Post once. Then read the comment back
and check that it is there and that the folds are folds, not plain `+++` or tags shown
as text. If they are not, fix the comment in place and say so.

When posting fails, say what failed, give the comment's text in the chat, and do not
try another place on your own.

## Output

Report in the developer's language, in two lines and nothing else:

1. What was posted and where: the comment as a link named by its ticket or pull
   request, how many findings by priority and how many items of simpler code and tests,
   and what the developer asked to add or leave out. Say that it replaced an older
   comment only when it did.
2. `Suggestions:` what this run showed could be better in this skill, the
   repository's instructions, or its checks, as
   [`../develop-task/references/suggestions.md`](../develop-task/references/suggestions.md)
   says, or `none`.

Leave out the path of the report, the commit, the parts of the report that never go
into the comment, and why the comment is in its language. For example:

```markdown
**Posted** to [UIB-6381](https://linear.app/uibakery/issue/UIB-6381#comment-…): P1 — 1, simpler — 7, your note on top; P2 left out, as you asked.
Suggestions: none.
```
