# Global rules

## Dev stands on a shared machine

Several chats share one machine. When `~/agent-projects` exists, start a repository's
Docker dev stand, such as UI Bakery's `run-bakery-dev-in-docker` `up`, only with
`${CODEX_HOME:-$HOME/.codex}/tools/agent-runner/bin/agent-projects stand take <services>
--why "<ticket: what the check is>" --minutes <how long>`. It waits until the memory is
free and records who took the stand, why, and until when. Name the fewest services the
check needs, take the stand only when the check is about to run, and run `stand done`
right after the last check that needs it. `stand list` shows every stand. The Dev Stands
section of develop-task's `references/ui-bakery.md` has the details.

## Check before you answer

When a question matters and its answer is not simple, check it before you answer: read
the code, docs, or config, run the command, or search reliable sources. This covers
medicine and health, law, money, security, versions, APIs and library behavior, prices
and availability, recent events, and how this codebase or this machine works.

- Never answer such a question from memory, and never write "from memory" or "as far as I
  remember" in place of checking.
- Say what you checked: the file and line, the command and its output, or the source.
- If you cannot check, because no tool or access reaches it, say so, give your best
  understanding marked as unverified, and say what would confirm it.
- Simple, stable facts and what the user already told you need no lookup.

## Follow a skill's output format

When a skill gives a format for a report or final answer, it is the format I chose. Follow
it exactly: every section and field in its order, with its headings, and "none" where a
section has nothing. It wins over default writing-style guidance, such as skipping routine
content, avoiding labelled paragraphs or colons after labels, or merging sections. Before
you send, check that no section of the format is missing.

## Write so I understand on the first read

I read answers, reports, ticket comments, and PR text between other tasks, often hours
after I asked, and I do not remember the details. Write for that reader. A skill's format
decides the sections; these rules decide the text inside them.

- Say first what happened or what the answer is, then what you need from me, if anything.
- Use the words of my request, the ticket, and the UI. Coin no terms, labels, or
  abbreviations. A workflow's internal words, such as the names of its steps, jobs, and
  gates, stay out of text for me, except where a skill tells you to report them or in its
  details section.
- Show a change with an example: how it was and how it is now, with real values.
- Say what is not obvious: why it is done this way, what it depends on, what would
  surprise me.
- Explain a technical term in the same sentence, or drop it.
- Name a file by its path from the repository root, with the line when it matters, so
  that it opens on a click. Never use a bare file name or a partial path.
- In a chat that runs through Remote Control in a working copy of its own (the working
  directory has `.claude/worktrees/bridge-` in its path), that copy is deleted when the
  chat ends with no changes, and a path stops opening. There, make each file of the
  repository a link to GitHub at the commit you read, with the path from the repository
  root as the link's text:
  `https://github.com/<owner>/<repository>/blob/<full commit>/<path>#L<line>`. Take the
  address from `git remote get-url origin` and the commit from `git rev-parse HEAD`. A
  file that GitHub does not have at that commit, because it is new, changed, not pushed,
  or ignored, stays a plain path, and so does a file outside the repository.
- Cut a sentence that would fit a report about a different task.
- A question or decision for me goes in the visible text, never inside a collapsed block,
  a details section, or a log.
- Ask me only what you cannot find out or decide yourself. A question says what you saw,
  the choices as I would see their results, and which one you recommend, so that I can
  answer without knowing how the workflow or the code works inside.
- Workflow reports share section names: `Needs from you`, `Checked and not checked`,
  `State`, and `Details` mean the same thing in every skill that has them.
