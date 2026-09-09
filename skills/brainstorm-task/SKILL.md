---
name: brainstorm-task
description: Create or revise a proportionate engineering task scope or feasibility recommendation from rough notes, voice-dump transcripts, an ambiguous idea, or an existing specification. Classify work as Spike, Bounded, or Architectural; scale repository and practice research to that class; and define delivery-slice interfaces when one coherent task spans separable responsibilities. When revising an existing scope, return both the complete new version and its meaningful changes. Use only when the user explicitly invokes $brainstorm-task; never activate it from a natural-language request alone. Supports an interactive brainstorm mode by default and an explicit autopilot mode with no user questions. Do not use when requirements are settled and the user asks to implement or review the change.
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

For interactive Bounded or Architectural work, D requires the approved
canonical scope. For a Spike, D means the requested feasibility findings and
recommendation are complete. In explicit autopilot mode it means the requested
report is complete, not approved.
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

Turn an incomplete idea or feasibility question into a proportionate,
repository-grounded result. A Spike ends with evidence and a recommendation. A
Bounded or Architectural path establishes the product intent, compares local
practice with general engineering practice when that comparison can change the
decision, considers viable approaches, and makes the boundary clear enough for
a later implementation workflow.

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

## Scope depth

After the initial understanding is confirmed in brainstorm mode, or internally
in autopilot mode, classify the work before choosing research and review depth:

- `Spike`: a feasibility or investigation question whose requested result is
  evidence and a recommendation, not implementation scope. Use the narrowest
  probe that can answer it. Do not manufacture a canonical implementation task.
- `Bounded`: one coherent change to an existing repository flow with a clear
  owner, limited blast radius, and no new subsystem or consequential interface
  redesign. Produce a concise scope in chat.
- `Architectural`: a new subsystem, a material restructuring, or a coherent
  task that changes multiple consequential interfaces or requires design
  choices whose tradeoffs affect later implementation. Use the full workflow.

In brainstorm mode, name the selected path and one concrete reason after the
user confirms the initial understanding. This is not a separate approval gate;
continue with the matching research, and let the user correct the classification
at the next checkpoint. When evidence exposes hidden complexity, upgrade the
path before continuing and explain why. Do not use a heavier path merely because
more ceremony is possible.

## Shared rules

- Treat unstructured notes and voice transcripts as valid input. Separate
  confirmed intent from tentative ideas, contradictions, and transcription
  noise. Do not turn every thought into a requirement.
- Exhaust read-only repository discovery before asking for information. Never
  ask where code lives, which module owns behavior, how the current logic
  works, or another question the repository can answer.
- Ask the user only about intent or a choice: desired behavior, user outcome,
  boundary, constraint, priority, risk tolerance, or completion evidence.
- Do not optimize brainstorm messages for a word count. Give enough context to
  understand the current point without decoding compressed phrasing. Keep each
  message focused on one mechanism, design concept, or decision. Do not surface
  speculative technical subproblems unless resolving them can change the task
  boundary, user-visible behavior, or chosen approach.
- Use the user's vocabulary and established repository or domain names. Do not
  coin umbrella terms, abbreviations, or architecture labels merely to shorten
  an explanation. When an exact repository identifier matters, first describe
  its concrete behavior and then give its name.
- Do not replace a prose explanation with formulas, arrow chains, pseudocode,
  or dense shorthand. A diagram may support an explanation after the behavior
  has been stated plainly, but it must not be the only explanation.
- Do not paste raw repository notes or specialist reports. Surface only facts
  that affect the decision.
- When the user corrects a premise, discard unapproved conclusions that depend
  on it and resume from the earliest affected stage.
- If the user asks for context or says they do not understand, do not advance
  or introduce another fork. Explain the missing concept in plain language
  with a concrete example, then restate the same question more simply.

Maintain a compact decision ledger with confirmed, assumed, open, rejected,
and later-work items. Show it only at checkpoints or when the user asks.

## Revising an existing scope

When the user asks to update an existing specification, scope, or prior
brainstorm result, treat the latest complete version they supplied, referenced,
or previously approved in the conversation as the baseline. Recover the exact
baseline from the source artifact or conversation history when available. Do
not reconstruct it from a loose summary. If no complete baseline is accessible,
ask the user for it before claiming an exact comparison.

Run the normal workflow, but focus research and questions on the proposed
changes and anything they invalidate. Preserve unchanged confirmed decisions.
Do not reopen them merely to repeat the original interview. Revisit an older
decision only when a new detail contradicts it, changes its consequences, or
makes its supporting repository evidence stale.

Maintain a baseline-to-current change ledger alongside the decision ledger.
Track meaningful requirement and contract changes as Added, Changed, or
Removed. For Changed items, retain both the old and new value. Ignore wording,
ordering, formatting, and section moves that do not change meaning. Never infer
that an omitted baseline item was removed unless the user explicitly removes it
or an approved new decision makes it impossible.

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

Choose specialist depth from the classified path:

- For a Spike, do not dispatch a specialist by default. Request one only for a
  concrete repository-practice or general-practice question whose answer can
  change feasibility or the recommendation.
- For Bounded repository work, dispatch `repo-practice-review` with the user
  intent and a focused repository question. Add `best-practice-review` only
  when local precedent is absent, weak, inconsistent, disputed, or creates a
  meaningful tradeoff that can change the scope or solution.
- For Architectural repository work, dispatch both roles. Give
  `best-practice-review` the user intent, repository evidence, and
  repo-practice result, and require it to identify where local practice should
  be followed or challenged.

Use `gpt-5.6-terra` high by default and `gpt-5.6-sol` high for novel,
cross-layer, high-risk, or difficult-to-validate questions. Keep specialists
read-only and prohibit recursive delegation. If a role required by the selected
path is technically unavailable, stop and name it. Do not imitate a missing
required independent review. An optional specialist being unavailable does not
block the path.

Synthesize one focused comparison with enough context to understand the
consequences before generating solution options:

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
their dependency order, and the smallest useful first task. Preserve the
remaining pieces as later work rather than silently dropping them.

- In brainstorm mode, explain the decomposition with enough context to
  distinguish the pieces, then ask the user to choose one current task. This is
  one interview question. Repeat affected repository and specialist research
  after the choice when the boundary changes.
- In autopilot mode, choose the smallest independently valuable first task,
  explain the choice, and list the other slices as later work.

## Define delivery slices

Do not confuse independently valuable tasks with implementation slices. Keep
separate user outcomes as separate current or later tasks under the
decomposition rule above. Within one coherent Bounded or Architectural task,
define delivery slices only when implementation still spans multiple separable
responsibilities that must be completed in dependency order.

Each delivery slice states:

- `Outcome`: the independently understandable result it establishes;
- `Consumes`: exact behavior or contracts required from earlier slices;
- `Produces`: exact behavior or contracts later slices may rely on;
- `Depends on`: earlier slices, or `none`;
- `Validation`: observable evidence that the slice delivered its contract.

Describe behavioral and interface contracts, not 2-5 minute coding steps. Do
not prescribe files, helpers, or code shape unless the user approved them as a
real constraint. Omit Delivery slices for one small coherent implementation.

## Brainstorm mode

### 1. Confirm understanding

The first response contains only a short readback of the user's idea in their
terms and a request to confirm or correct it. Do not inspect the repository,
ask a substantive question, identify a design fork, or propose a solution in
that response.

Wait for confirmation. A correction replaces the provisional understanding.

### 2. Classify, research, and compare

Name the path and reason, then run the matching repository and practice research
above.

For a Spike, establish the exact question and evidence needed to answer it,
asking one intent question only when necessary. Complete the targeted read-only
investigation, return the findings and recommendation, and stop. Do not continue
into implementation requirements, scope approval, or delivery slices unless the
user turns the result into a build request.

For Bounded or Architectural work, show the focused comparison with enough
explanation to understand its consequences, then wait for the user's reaction
before the requirements interview. Do not show solution options yet.

### 3. Interview one decision at a time

For Bounded and Architectural work, run a requirements interview even when the
initial description seems detailed.
Ask exactly one focused question per message. Do not repeat facts already
settled by the user or repository. The one-question rule limits how many
decisions are discussed at once; it does not limit the explanation needed
before the question. Use the interview to establish every relevant high-impact
decision among:

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
the actual decision question. Do not compress prerequisites merely to reach the
question. Explain every linked premise needed for the current decision in full.
Split the explanation across turns only when a premise itself requires a user
decision; never split it only to satisfy a length target.

Questions have no numeric quota. Ask another only when its answer can change
the goal, boundary, approach, risk, or acceptance criteria. Even when all fields
appear answered, use at least one question to confirm the highest-impact
assumption.

If an answer changes the repository boundary or the basis of the practice
comparison, repeat the affected repository inspection and any specialist
reviews required by the current path. Show the corrected comparison before
continuing toward options.

### 4. Compare approaches

After the interview is complete, generate possible approaches and filter them
before showing any to the user. Bounded work needs only materially different
directions that can change the outcome; Architectural work warrants a broader
comparison when real alternatives exist. An approach is viable only when it satisfies
the confirmed goal, every hard constraint, required behavior preservation, and
the approved task boundary. Discard anything already rejected by the user or
the research. A technically possible workaround is not viable when it widens
the task, changes behavior that must stay unchanged, or adds risk without a
benefit relevant to the confirmed goal.

Never manufacture alternatives to reach a quota:

- If two or more materially different viable approaches remain, present only
  those whose tradeoffs could realistically change the decision. Normally this
  will be two or three. Explain each without shorthand, lead with a
  recommendation, and ask the user to choose, combine, or revise them.
- If exactly one viable approach remains, say that the confirmed constraints
  leave one direction and present only that direction. Mention discarded ideas
  under Rejected only when their exclusion needs to be recorded. Do not format
  them as choices.
- If no viable approach remains, return to the affected research or interview
  decision instead of weakening a confirmed constraint silently.

When the user already confirmed the same technical direction after seeing the
evidence and consequences, record it as chosen and proceed to scope approval.
Do not reopen a settled choice merely because this workflow has reached the
approach stage. Ask for confirmation only when it can still change the
direction.

### 5. Approve the scope

Before presenting the first approval, perform a final synthesis audit. Re-read
all user messages and annotations since invocation and rebuild the decision
ledger from those source messages, not from earlier summaries. The latest
explicit correction wins. Preserve exact contract decisions such as numeric
limits, literal UI copy, filenames, permissions, error behavior, and complete
field or item lists. If a context reset or compaction occurred, use available
history tools to recover the earlier user messages and annotations before the
audit; do not treat a compacted summary as the source of truth.

Map every confirmed decision to Goal, Requirements, Validation, Output
contract, Implementation constraints, Out of scope, Later work, Open questions,
Assumptions, or Rejected. Resolve contradictions and do not present the approval
while a confirmed decision remains unmapped. Keep this coverage mapping
internal unless the user asks to see it. Repository facts, practice findings,
possible risks, and rejected ideas are not confirmed requirements merely
because they appeared during research.

Present no more approval checkpoints than the task needs:

- For Bounded work, present one compact scope checkpoint containing Goal,
  Requirements, Validation, and any necessary Output contract or still-open
  technical direction. Do not create a second approval checkpoint.
- For Architectural work, first present that requirements checkpoint. Add a
  separate technical direction checkpoint only when an unresolved
  implementation choice or hard technical constraint could materially change
  the result. Include only the repository evidence needed to understand that
  decision, and skip it when the direction is already confirmed.

Keep the requirements checkpoint concise, but never compress or omit an exact
decision to meet a word target. Let a real Output contract grow to the detail
required for implementation. A requirements change invalidates dependent
technical decisions.

After the required approvals, repeat the synthesis audit for decisions
introduced or corrected during approval. Generate the canonical scope from the
audited decision ledger rather than by summarizing the approval messages.

Then return the revision summary defined below when a baseline exists, followed
by the canonical scope. For a new scope, return only the canonical scope. Do
not append a handoff prompt or start implementation.

## Autopilot mode

Do not send intermediate questions or approval checkpoints. Internally:

1. Form the same provisional understanding.
2. Classify the path and complete its matching repository and practice research.
3. For a Spike, complete the targeted investigation and return evidence plus a
   recommendation without generating a canonical implementation scope.
4. For Bounded or Architectural work, decompose an oversized idea and select
   the smallest useful first task.
5. Generate the same requirements questions and answer each from, in order,
   the user's words, repository evidence, and explicit assumptions.
6. Re-run affected research when an internal answer changes the boundary.
7. Apply the same viability filter as interactive mode. Compare materially
   different approaches when more than one survives; when only one survives,
   choose it without inventing alternatives.

When two interpretations remain equally plausible, choose the smaller
independently useful scope. Never let best-practice guidance invent product
requirements. Mark every answer not supported by the user or repository as an
assumption.

Return a structured report whose length follows task complexity without
repetition. A Spike ends with its evidence and recommendation. For Bounded or
Architectural work, keep repository/practice findings and approach reasoning
separate from the canonical scope; include only the findings needed to justify
the recommendation, followed by that scope. When a baseline exists, include the
same revision summary as interactive mode. The recommendation is the agent's
working conclusion, not user approval.

## Revision summary

Before the complete canonical scope, show `Changes from previous version` with
only meaningful Added, Changed, and Removed items. Omit empty categories. Keep
it compact, but preserve exact names, values, limits, and contract details. For
each Changed item, use `old -> new` so the user does not need to compare two
full documents. If nothing material changed, say so explicitly.

Derive this summary from the audited baseline-to-current ledger, not by diffing
the final prose. The complete canonical scope remains authoritative. The change
summary is a review aid and must not contain requirements missing from the full
scope.

## Canonical scope

The canonical scope is an implementation task specification, not a record of
the research process. Always include Goal, Requirements, and Validation. Add
the other sections only when their stated condition applies:

```text
Goal:
Requirements:
Validation:
Output contract:            [only for a substantial exact artifact or contract]
Implementation constraints: [only for approved constraints that prevent a wrong implementation]
Delivery slices:            [only for one coherent task with separable dependent responsibilities]
Out of scope:               [only for explicit or credible boundary ambiguities]
Later work:                 [only for explicitly deferred work]
Open questions:             [only when unresolved]
Assumptions:                [only in autopilot or when a decision could not be obtained]
```

Write Goal as one outcome sentence. Put user-visible behavior, permissions,
compatibility rules, boundaries, and other accepted behavior in Requirements.
Put observable completion evidence, required test levels, permission matrices,
and edge cases in Validation. Do not reduce Validation to generic activities
such as "add tests" when exact scenarios were agreed.

Implementation constraints contain only approved technical rules whose
omission could lead to a materially wrong solution. A repository owner, file,
class, helper, or test location is not a constraint by default. Include an exact
location only when the user required it or the location itself is part of the
approved boundary.

When Delivery slices are present, give every slice an Outcome, Consumes,
Produces, Depends on, and Validation entry. Keep exact approved names, values,
formats, and relationships. This section defines implementation handoffs, not a
file-by-file coding plan; leave local code shape to the later implementation
workflow.

Do not include repository evidence, general-practice commentary, rejected
approaches, generic risks, or lists of files and unrelated subsystems that need
no change. Keep those in the research discussion and internal ledger. Put an
item in Out of scope only when it records an explicit user decision or resolves
a credible ambiguity considered during the brainstorm. Do not manufacture
negative requirements by listing everything the implementation should leave
untouched.

State each decision once in the most specific section. Do not repeat the same
rule as a user problem, behavior, acceptance criterion, scope item, contract,
and risk. Keep confirmed decisions separate from assumptions. The result must
be short enough to review without rereading the discovery conversation, while
preserving every exact requirement and required validation case.
