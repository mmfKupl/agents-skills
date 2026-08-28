---
name: brainstorm-task
description: Turn rough notes, voice-dump transcripts, or an ambiguous repository engineering idea into a concise task scope through repository research, independent repository-practice and best-practice review, requirements interviewing, and solution comparison. Use only when the user explicitly invokes $brainstorm-task; never activate it from a natural-language request alone. Supports an interactive brainstorm mode by default and an explicit autopilot mode with no user questions. Do not use when requirements are settled and the user asks to implement or review the change.
---

# Brainstorm task

## Writing quality

Before drafting user-facing prose, read [`../unslop/SKILL.md`](../unslop/SKILL.md)
and apply its relevant guidance. Preserve the user's terminology and exact
wording when they affect the task.

## Task title

Task titles are a best-effort sidebar indicator, never a workflow gate.
With a known ticket, use `<ticket-id> <description>: <status> <type>`.
Without one, use `<description>: <status> <type>`.
Write the ticket ID as plain text, never in square or round brackets.
For example: `UIB-5295 Storybook update: W brainstorm`.
When reusing a title with a bracketed ticket ID, remove those brackets.
Prefer a two-word description, with three words maximum; describe the subject
without filler such as "task", "implementation", or "scope".

Use `brainstorm` as the type when this is the active user-requested workflow.
An embedded review, worker, or validation step must not replace the outer
workflow's type or mark its task done. Only the user-facing coordinator owns
the current task's title; change type when a different requested workflow
actually starts.

Use only these statuses:

- `W` Working: progressing independently, including waiting for tests, CI, or
  agents that the workflow will handle without a user reply.
- `R` Reply needed: pausing for the user's answer, choice, or approval.
- `B` Blocked: stopped by an obstacle such as missing access or an unavailable
  dependency. Use R instead when the next step is a user decision.
- `D` Done: the requested work is complete, not simply the current turn.

For interactive brainstorm, D requires the approved canonical scope; in
explicit autopilot mode it means the requested report is complete, not approved.
Use W again when work resumes. Recoverable errors remain W while being handled;
there is no E status. A title-tool failure never changes the work's status.

At entry, take one small `list_threads` snapshot when available. Reuse the
most recent matching description for the same explicit ticket, shortening it
to the word limit if necessary; otherwise choose from known task context.
Recognize current titles and both older `<description>: <type>` and
`<type>: <description>` formats. Keep the chosen description stable.
Best-effort align descriptions of matching tasks within the same short budget,
preserving each task's own type and existing status. Never guess another
task's status, add one to a legacy title, or rename unrelated tasks.

Update the current title with `set_thread_title` at entry and when its status
or active workflow changes, including before asking a blocking question or
sending the final result. Skip already-confirmed identical titles. A successful
tool response confirms the update; do not add a separate readback after success.

Keep this cheap: use bounded/asynchronous execution with a shared foreground
wait budget of about two seconds per checkpoint for all title tools, including
listing and readback. If unavailable, slow, or failed, continue the real work;
defer further title calls and retain only the latest desired title as pending.
Do not stack in-flight title writes. At a later natural work checkpoint, make
at most one deferred verification/retry per turn, plus one final attempt before
yielding to the user. Check any existing attempt first; if its outcome is
unknown, use a single small snapshot before retrying. Replace stale pending
states with the current one. Apart from the final attempt, leave further retries
for the next turn.
Do not repeatedly list tasks, poll, sleep, create a reminder, diagnose the app,
or ask the user for help solely to update a title. Do not claim success without
confirmation. Titles may be stale while the desktop app is offline.

These narrow Codex title updates are permitted even in read-only workflows;
they do not authorize ticket, PR, code, or other external changes.

## Outcome and boundary

Turn an incomplete idea into one repository-grounded task scope. Establish the
product intent, compare local practice with general engineering practice,
consider viable approaches, and make the boundary clear enough for a later
implementation workflow.

This is a read-only discovery workflow. Do not edit product code, tests,
configuration, tickets, or external systems. Do not start implementation,
write an implementation plan, or invoke an implementation workflow. Create a
scope document only when the user separately asks for one after scoping.

Invocation authorizes read-only delegation to `repo-practice-review` and
`best-practice-review`. Do not delegate to a writer.

## Modes

Use `brainstorm` unless the user explicitly requests `autopilot` through
`$brainstorm-task autopilot` or an unambiguous phrase such as "без вопросов",
"сам реши", or "пройди самостоятельно". Do not infer autopilot from a long or
detailed input.

- `brainstorm` collaborates through small checkpoints and exactly one question
  per interview turn.
- `autopilot` performs the same research, decomposition, interview, and option
  analysis internally. It asks no questions and waits for no approvals.

## Shared rules

- Treat unstructured notes and voice transcripts as valid input. Separate
  confirmed intent from tentative ideas, contradictions, and transcription
  noise. Do not turn every thought into a requirement.
- Exhaust read-only repository discovery before asking for information. Never
  ask where code lives, which module owns behavior, how the current logic
  works, or another question the repository can answer.
- Ask the user only about intent or a choice: desired behavior, user outcome,
  boundary, constraint, priority, risk tolerance, or completion evidence.
- Keep ordinary brainstorm messages under roughly 120 words and at most five
  short bullets. The user may ask for more detail.
- Introduce at most one new mechanism, design concept, or decision in a
  message. Do not surface speculative technical subproblems unless resolving
  them can change the task boundary, user-visible behavior, or chosen approach.
- Do not paste raw repository notes or specialist reports. Surface only facts
  that affect the decision.
- When the user corrects a premise, discard unapproved conclusions that depend
  on it and resume from the earliest affected stage.
- If the user asks for context or says they do not understand, do not advance
  or introduce another fork. Explain the missing concept in plain language
  with a concrete example, then restate the same question more simply.

Maintain a compact decision ledger with confirmed, assumed, open, rejected,
and later-work items. Show it only at checkpoints or when the user asks.

## Repository and practice research

After the initial understanding is confirmed in brainstorm mode, or internally
in autopilot mode:

1. Read applicable `AGENTS.md` and repository documentation.
2. Inspect `git status --short --untracked-files=all`. Treat existing changes
   as user-owned and do not assume they belong to the proposed task.
3. Find the likely owner, entry boundary, related modules, nearby production
   examples, reusable helpers, contracts, tests, and focused validation tools.
   Inspect recent history when it helps establish the current pattern.
4. Distinguish strong local practice from weak, copied, inconsistent,
   outdated, or absent precedent.
5. Dispatch `repo-practice-review` with the user intent and focused repository
   question. Require repository evidence.
6. Dispatch `best-practice-review` with the user intent, repository evidence,
   and repo-practice result. Require it to identify where local practice should
   be followed or challenged.

Both specialists are mandatory for repository tasks. Use `gpt-5.6-terra` high
by default and `gpt-5.6-sol` high for novel, cross-layer, high-risk, or
difficult-to-validate tasks. Keep both specialists read-only and prohibit
recursive delegation. If either role is technically unavailable, stop and name
the missing role. The main agent must not imitate the missing independent
review.

Synthesize one compact comparison before generating solution options:

- how the repository currently handles the problem;
- what strong general practice would normally do;
- where the two agree, conflict, or leave no precedent;
- which constraints and decisions this creates for the task.

Label repository facts, general guidance, and the main agent's reconciliation
as different kinds of evidence.

## Decompose oversized ideas

Before the detailed requirements interview, decide whether the idea contains
multiple independently valuable tasks. Indicators include separate user
outcomes, independently deployable subsystems, unrelated owners, or a boundary
too large to validate as one change.

Do not refine an oversized idea as one task. Identify the independent pieces,
their dependency order, and the smallest useful first slice. Preserve the
remaining pieces as later work rather than silently dropping them.

- In brainstorm mode, show the short decomposition and ask the user to choose
  one current task. This is one interview question. Repeat affected repository
  and specialist research after the choice when the boundary changes.
- In autopilot mode, choose the smallest independently valuable first slice,
  explain the choice, and list the other slices as later work.

## Brainstorm mode

### 1. Confirm understanding

The first response contains only a short readback of the user's idea in their
terms and a request to confirm or correct it. Do not inspect the repository,
ask a substantive question, identify a design fork, or propose a solution in
that response.

Wait for confirmation. A correction replaces the provisional understanding.

### 2. Research and compare

Run the repository and practice research above. Show the compact comparison and
wait for the user's reaction before the requirements interview. Do not show
solution options yet.

### 3. Interview one decision at a time

Run a requirements interview even when the initial description seems detailed.
Ask exactly one focused question per message. Do not repeat facts already
settled by the user or repository. Use the interview to establish every
relevant high-impact decision among:

- desired outcome and affected users;
- observable behavior and important current behavior to preserve;
- required scope, optional scope, and explicit exclusions;
- compatibility, data, permissions, rollout, failure, and operational
  constraints;
- observable evidence that would prove the task complete.

Ask only questions the user can answer meaningfully from the current message.
Before asking about a new mechanism, label, or abstract tradeoff:

- explain it in plain language before relying on its name;
- state why this decision matters and what changes with the answer;
- give at least one concrete example from the current task, or compare the
  options through concrete consequences;
- recommend a default when repository evidence or general practice supports
  one, and explain the reason briefly.

Do not ask the user to approve an unexplained term such as a policy, marker,
lifecycle, or opt-in. Do not use "does that make sense?" as a substitute for
the actual decision question. If the required context does not fit concisely,
explain one premise first and defer the decision rather than compressing
several new ideas into a wall of text.

Questions have no numeric quota. Ask another only when its answer can change
the goal, boundary, approach, risk, or acceptance criteria. Even when all fields
appear answered, use at least one question to confirm the highest-impact
assumption.

If an answer changes the repository boundary or the basis of the practice
comparison, repeat the affected repository inspection and both independent
reviews. Show the corrected comparison before continuing toward options.

### 4. Compare approaches

After the interview is complete, present two or three genuinely different
viable approaches in one concise set. For each include its basic shape, the
tradeoff that distinguishes it, and any tension with repository practice or an
explicit constraint. Lead with a recommendation and explain why it fits the
confirmed goal. Include a smaller approach when credible. Ask the user to
choose, combine, or revise the approaches.

### 5. Approve the scope in two parts

Before presenting the first approval, perform a final synthesis audit. Re-read
all user messages and annotations since invocation and rebuild the decision
ledger from those source messages, not from earlier summaries. The latest
explicit correction wins. Preserve exact contract decisions such as numeric
limits, literal UI copy, filenames, permissions, error behavior, and complete
field or item lists. If a context reset or compaction occurred, use available
history tools to recover the earlier user messages and annotations before the
audit; do not treat a compacted summary as the source of truth.

Map every confirmed decision to Product boundary, Output contract, Technical
direction, Validation, Later work, or Rejected. Resolve contradictions and do
not present the approval while a confirmed decision remains unmapped. Keep this
coverage mapping internal unless the user asks to see it.

Present and approve these checkpoints separately:

1. Product boundary: goal, affected user, observable behavior, in scope, out of
   scope, later work, and acceptance criteria. When the task defines a
   substantial artifact, schema, API, event, configuration, or data format,
   include a separate Output contract in the same checkpoint with its exact
   names, fields, formats, limits, and required content.
2. Technical direction: repository owner and evidence, chosen approach,
   contracts to preserve, risks, and validation direction.

Keep the Product boundary concise, but never compress or omit exact decisions
to meet a word target. Let the Output contract grow to the detail required for
implementation and approve it together with the Product boundary. A change to
the first checkpoint invalidates dependent parts of the second.

After both approvals, repeat the synthesis audit for decisions introduced or
corrected during approval. Generate the canonical scope from the audited
decision ledger rather than by summarizing the approval messages.

After both approvals, return only the canonical scope defined below. Do not
append a handoff prompt or start implementation.

## Autopilot mode

Do not send intermediate questions or approval checkpoints. Internally:

1. Form the same provisional understanding.
2. Complete repository and practice research.
3. Decompose an oversized idea and select the smallest useful first slice.
4. Generate the same requirements questions and answer each from, in order,
   the user's words, repository evidence, and explicit assumptions.
5. Re-run affected research when an internal answer changes the boundary.
6. Identify all genuinely viable approaches, compare them, and choose a
   recommendation.

When two interpretations remain equally plausible, choose the smaller
independently useful scope. Never let best-practice guidance invent product
requirements. Mark every answer not supported by the user or repository as an
assumption.

Return a structured report whose length follows task complexity without
repetition. Include the repository/practice comparison, all viable approaches,
the recommendation, later work, assumptions, unresolved risks, and the
canonical scope. The recommendation is the agent's working conclusion, not
user approval.

## Canonical scope

Use this shape, omitting empty fields when that improves readability:

```text
Goal:
Affected users and problem:
User-visible behavior:
Acceptance criteria:
In scope:
Output contract:
Out of scope:
Later work:
Relevant repository evidence:
Repository versus best practice:
Chosen direction:
Contracts and constraints:
Validation expectations:
Assumptions and unresolved risks:
```

Acceptance criteria must describe observable evidence, not implementation
activity. Keep confirmed decisions separate from assumptions. The result must
be short enough to review without rereading the discovery conversation.
