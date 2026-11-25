# UI Bakery Repository Notes

Load this reference only after repository evidence identifies the UI Bakery monorepo.

- The tracker is Linear, reached through the Linear connection of this application.
  Create the project with `--tracker linear`.
- What the statuses of the UIB team mean for the developer:
  - `In Review`, assigned to the developer by someone else: a review is wanted, so
    the step is `$review-task`.
  - `In AI Review`: an agent the developer started has finished and waits for their
    review. Show it; start a review only when the developer asks.
  - `In Progress`, assigned to the developer: work is wanted. Decide between
    `$brainstorm-task` and development.
- A ticket that the developer sends for work without naming the step goes through
  the check of the ready trigger `my progress`, whatever its status and whether or
  not that trigger is on in the project:
  `agent-projects watch add <project> <ticket> --trigger "my progress"`. The check
  sorts it as large or unclear work, small work, feedback on work done here, or a
  continuation, and starts what the trigger names for that.
- The ready trigger `my review` covers the first of these statuses: it starts
  `$review-task` when someone else moved the ticket to `In Review` and the ticket is
  assigned to the developer.
- Development always runs as `$develop-please $develop-task <ticket>`. `$develop-please`
  lives in the UI Bakery repository and owns the ticket's status, the pull request,
  and the reports in Linear.
- No skill moves a ticket's status by itself: during development `$develop-please`
  does, and `$project-master` does when the developer asks for it in its chat.
  `$project-scope` never does.
- "Return the ticket to its author" after a review means both steps: assign the
  ticket to the author and move it to `In Progress`. When the author moves it back to
  `In Review` for the developer, `my review` starts the next review.
- Agents post in Linear under the developer's own account, with nothing that marks an
  agent. A comment that starts with `$develop-please:` is an agent's report, not the
  developer's words.
