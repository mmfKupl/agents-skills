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
- The ready trigger `my review` covers the first of these statuses: it starts
  `$review-task` when someone else moved the ticket to `In Review` and the ticket is
  assigned to the developer.
- Development always runs as `$develop-please $develop-task <ticket>`. `$develop-please`
  lives in the UI Bakery repository and owns the ticket's status, the pull request,
  and the reports in Linear.
- Only `$develop-please` moves a ticket's status. `$project-master` and
  `$project-scope` never do.
- Agents post in Linear under the developer's own account, with nothing that marks an
  agent. A comment that starts with `$develop-please:` is an agent's report, not the
  developer's words.
