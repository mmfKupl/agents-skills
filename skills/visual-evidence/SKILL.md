---
name: visual-evidence
description: "Show how a change looks and behaves: walk its main scenarios by hand on a running build, record video and screenshots, keep the matching API or agent output, and post them where the developer will see them. Use when the user asks to see a change, and from develop-task, develop-please, develop-draft, brainstorm-task, and review-task when a change has visible or runtime behavior."
---

# Visual Evidence

The developer should see the result without building it locally. Evidence shows the
change working, scenario by scenario, as a user or a caller of the API would see it.

## What to capture

Choose by what the change touches; a change can need several:

- **UI:** a video of each main scenario walked by hand, and screenshots of its key
  states. Add a `before` screenshot from the base build when the change alters
  something that existed.
- **API, MCP, or jobs:** a short readable log of request and response for each
  scenario. Add a screenshot when the result also shows in the UI.
- **Agent or chat behavior:** the agent conversation and a screenshot of what it
  produced.
- **Nothing visible:** one line saying why, instead of evidence.

The scenarios come from the requirements: the main path first, then the cases the
change exists for. Keep the API responses behind each screenshot: a screenshot alone
cannot tell a rounding rule from a stale value. When what you see differs from what you
expected and the requirements do not settle it, report it as a question, not as a bug.

## How to capture

Main does this, since runner jobs have no network. Run against the closest build that
contains the change: the PR preview once it exists, otherwise a local stand or the
repository's Storybook.

- Walk the scenarios with a scratch Playwright spec that reuses the repository's e2e
  fixtures and page objects for sign-up, sign-in, and navigation. Put it in a disposable
  worktree at the change's commit, never in the task's worktree, and never commit it.
- Install that worktree's own dependencies and the Playwright browser it pins; another
  checkout's `node_modules` can be weeks older.
- Turn on video, a short `slowMo`, and the e2e viewport, and log the API responses the
  scenario depends on. Wait for a visible state, not a fixed time, before each screenshot.
- A scratch spec breaks on small details, such as a menu that Escape does not close.
  Fix it and rerun; a failed capture is not evidence.

Remove the worktree and temporary files when done.

## Storybook

When the build serves Storybook and the change touches components that have stories,
post a separate comment with a direct link to each affected story. Take the story IDs
from Storybook's `index.json`, and say for each link what to look at or click, for
example "open the popover, check the `this chat` badge".

## Where to post

- Upload files to the tracker, for Linear with `prepare_file_upload` and a PUT of the
  raw bytes, and post them in a ticket comment: the video and screenshots first with one
  line per scenario, API logs and details in a collapsible block. Videos stay `webm`.
- Link the same comment from the PR when the outer workflow owns a PR.
- In a chat app that can show files, also send the files to the developer.
- Ask before posting on a ticket or PR that another person owns, unless the active
  workflow already authorizes its comments.

Never paste local paths as evidence.

## Mockups before code

For brainstorm-task and develop-draft, when the idea is visual, try it before code
exists: change a story or a page in a disposable worktree, run Storybook or a local
stand, and capture one or two variants. Show them with the proposal, say they are
mockups, and commit nothing from that worktree.

## Repository specifics

A repository's own workflow skill, such as develop-please in UI Bakery, says which
stands exist, how to sign in, and which comments it owns. It wins over this skill.
