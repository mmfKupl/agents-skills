---
name: visual-evidence
description: "Show how a change looks and behaves: walk its main scenarios by hand on a running build, record video and screenshots, keep the matching API or agent output, and post them where the developer will see them. Use when the user asks to see a change, and from develop-task, develop-please, develop-draft, brainstorm-task, and review-task when a change has visible or runtime behavior."
---

# Visual Evidence

The developer should see the result without building it locally. Evidence shows the
change working, scenario by scenario, as a user or a caller of the API would see it.
Recording a scenario does not check it: every capture is also examined for defects
before it is posted (Inspect what you captured).

## What to capture

Choose by what the change touches; a change can need several:

- **UI:** a video of each main scenario walked by hand, and screenshots of its key
  states. Add a `before` screenshot from the base build when the change alters
  something that existed. Take `before` and `after` with the same account, data,
  viewport, and UI state, so that the change is the only difference between them.
- **API, MCP, or jobs:** a short readable log of request and response for each
  scenario. Add a screenshot when the result also shows in the UI.
- **Agent or chat behavior:** the agent conversation and a screenshot of what it
  produced.
- **Nothing visible:** one line saying why, instead of evidence.

The scenarios come from the requirements: the main path first, then the cases the
change exists for. Include the states a user can reach on the changed screen, such as
hover, keyboard focus, disabled, loading, empty, and error, and the narrow width when the
layout can be narrow. Keep the API responses behind each screenshot: a
screenshot alone cannot tell a rounding rule from a stale value. When what you see
differs from what you expected and the requirements do not settle it, report it as a
question, not as a bug.

## Write down what to expect first

Before the walkthrough, list what the developer should see at each key state of each
scenario: which elements are there, their text and state, and what must stay as it was.
Take the list from the requirements, the design, and the same screen on the base build,
not from the new code: a list written from the code can only confirm what was built.

## How to capture

Main does this, since runner jobs have no network. Run against the closest build that
contains the change: the PR preview once it exists, otherwise a local stand or the
repository's Storybook.

- Walk the scenarios with a scratch Playwright spec that reuses the repository's e2e
  fixtures and page objects for sign-up, sign-in, and navigation. Put it in a disposable
  worktree at the change's commit, never in the task's worktree, and never commit it.
  Only when the change is not committed yet, keep the spec in a git-ignored folder of
  the task's worktree, and remove it when done.
- Install that worktree's own dependencies and the Playwright browser it pins; another
  checkout's `node_modules` can be weeks older.
- Turn on video, a short `slowMo`, and the e2e viewport, and log the API responses the
  scenario depends on. Wait for a visible state, not a fixed time, before each screenshot.
- A scratch spec breaks on small details, such as a menu that Escape does not close.
  Fix it and rerun; a failed capture is not evidence.
- Take a cropped or zoomed screenshot after the video has stopped, or cut it from the
  full screenshot: one taken during the recording leaves a grey frame in the video.

Remove the worktree and temporary files when done, after the inspection.

## Inspect what you captured

A screenshot nobody examined proves only that the page loaded. Before posting, a fresh
`visual-review` agent with no conversation history, the inspector, examines every file.
It wrote neither the change nor the capture script, and it changes nothing. This skill
authorizes it. The calling workflow starts it the way it starts its other roles: through
the runner where the workflow uses the runner, otherwise as a subagent. Give it the model
of the workflow's final reviewer, or the session's own model on a direct request, not a
cheaper model that ran the capture.

- Give it the expected list, every screenshot with its `before` pair when there is one,
  and frames from every video, as absolute file paths. Do not give it your notes or your
  opinion of the result.
- No model watches a video. Extract frames, for example
  `ffmpeg -i <video> -r 5 <directory>/frame-%04d.png`; the `ffmpeg` that Playwright
  installs is enough, and it has no `fps` filter. Pass only the frames around each click,
  open, close, and load, a few before and a few after, about ten per video: every frame
  is read as an image, and a whole recording costs far more than the rest of the run.
  Without `ffmpeg`, rerun the scenario with a screenshot every 100 to 200 ms around those
  moments.
- Its role file tells it what to do with each image: describe what it shows, list every
  difference from the expected list and from the `before` image, and go through a basic
  checklist: text is complete and readable, the layout holds, each state matches similar
  controls nearby, the screen is consistent, values match the API responses, and nothing
  jumps or flickers between frames. Pass the API responses that belong to a screenshot
  with it.

What the inspector reports as wrong is a defect of this change, unless the `before` image
shows the same problem: then it is only a follow-up note. Where a defect goes depends on
who called this skill:

- an implementation workflow returns it through its own fix path, within its limit on fix
  rounds, then recaptures and has the new files inspected;
- `review-task` reports it as a finding;
- on a direct request, show it to the developer with the image.

A defect is closed when its fix passes a new inspection, or when the reviewer or the
developer accepts it. What the inspector cannot settle, such as taste or an intended
redesign, goes to the developer as a question with the image. If no fresh agent can open
images, read the `visual-review` role file in your runtime's `agents` folder, inspect each
file yourself, one by one, the way it describes, and say so.

## Storybook

When the build serves Storybook and the change adds or touches stories, or components
that have them, post a Storybook comment of its own: a direct link to each affected story,
with what to look at or click, for example "open the popover, check the `this chat`
badge". Take the story IDs from Storybook's `index.json`. Post it before the final report,
never inside the report or one of its collapsible blocks, and link it from the report.

## Where to post

Post only after the inspection, and add one line with it: what was inspected, and what it
found and how that was resolved, or that it found nothing.

- Upload files to the tracker, for Linear with `prepare_file_upload` and a PUT of the
  raw bytes, and post them in a ticket comment: the video and screenshots first with one
  line per scenario, API logs and details in a collapsible block.
- Trackers such as Linear show an uploaded video only as a plain link, which is easy to
  miss. Put each video on its own line that says it is a video, what it shows, and how
  long it is, for example `▶ Video (40 s): sign in, open the app, the 500 page appears`,
  next to the screenshot of its final state. Never hide a video link inside a sentence or
  a collapsible block.
- Link the same comment from the PR when the outer workflow owns a PR.
- In a chat app that can show files, also send the files to the developer.
- Ask before posting on a ticket or PR that another person owns, unless the active
  workflow already authorizes its comments.

Never paste local paths as evidence.

## Mockups before code

For brainstorm-task and develop-draft, when the idea is visual, try it before code
exists: change a story or a page in a disposable worktree, run Storybook or a local
stand, and capture one or two variants. Show them with the proposal, say they are
mockups, and commit nothing from that worktree. A mockup needs no inspector: look at it
yourself before showing it.

## Repository specifics

In the UI Bakery monorepo, read [`references/ui-bakery.md`](references/ui-bakery.md): its
stands, sign-in, Storybook, and preview MCP rules, which replace `$develop-please`'s
Screenshot Evidence. In another repository, its own workflow skill says which stands exist
and how to sign in.
