---
name: brainstorm-task
description: Create or revise a repository-grounded engineering scope or feasibility recommendation from notes, an idea, or a spec. Use only when the user explicitly writes `$brainstorm-task` (or `/brainstorm-task` in Claude Code).
---

# Brainstorm task

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else, including the entry task title. It maps Codex tools, model
names, task titles, and delegation to Claude Code; every gate and rule in this
skill still applies.

## Task title

At entry, read [`../chat-title/SKILL.md`](../chat-title/SKILL.md) and follow it with
the type `brainstorm`. For interactive Bounded or Architectural work, `D` requires the approved canonical
scope. For a Spike, `D` means the requested feasibility findings and recommendation
are complete. In explicit autopilot mode it means the requested report is complete,
not approved.

## Outcome and boundary

Read-only: do not edit product code, tests, configuration, tickets, or
external systems, implement, write an implementation plan, or invoke an
implementation workflow. Write a scope document only if asked after scoping.
Invocation authorizes read-only delegation to `repo-practice-review`,
`best-practice-review`, `test-review`, and the `code-simplicity-review` cost check. Never
delegate to a writer.

## Embedded discovery

When the user explicitly combines this skill with `$develop-task` for one task,
read [`../develop-task/references/composed-workflows.md`](../develop-task/references/composed-workflows.md).
Main runs read-only discovery inside that run, without a second orchestrator,
inheriting its backend, routing matrix, model ceiling, requirement sources, and
usage accounting before any specialist dispatch, not the standalone model
defaults below. Hand the scope to the coordinator for persistence and
implementation only under the explicit combined request. Interactive
checkpoints still apply; develop-task does not imply autopilot. A Spike does
not authorize implementation. Do not mark the outer task done when discovery
finishes.

## Modes

Use `brainstorm` unless the user explicitly requests `autopilot` through
`$brainstorm-task autopilot` or an unambiguous phrase such as "без вопросов",
"сам реши", or "пройди самостоятельно". A long or detailed input does not imply
autopilot. Autopilot does the same work internally, with no questions or
approvals.

## Scope depth

Once the initial understanding is confirmed (internally in autopilot), classify the work:

- `Spike`: a feasibility or investigation question answered with evidence and a
  recommendation from the narrowest probe, with no canonical scope.
- `Bounded`: one coherent change to an existing flow with a clear owner,
  limited blast radius, and no new subsystem or consequential interface
  redesign. A concise scope in chat.
- `Architectural`: a new subsystem, a material restructuring, or changes to
  multiple consequential interfaces or design choices whose tradeoffs affect
  later implementation. The full workflow.

Upgrade the path, saying why, when evidence exposes hidden complexity; never
pick a heavier one for ceremony.

## Shared rules

- Accept unstructured notes and voice transcripts; separate confirmed intent
  from tentative ideas, contradictions, and transcription noise.
- Exhaust read-only discovery first; never ask what the repository can answer
  (where code lives, who owns behavior, how logic works). Ask only about
  intent or a choice: behavior, user outcome, boundary, constraint, priority,
  risk tolerance, or completion evidence.
- Give enough context to understand the point, one mechanism, concept, or
  decision per message, never compressed for a word count. Raise a speculative
  technical subproblem only when it can change the boundary, user-visible
  behavior, or approach.
- Use the user's vocabulary and established names; coin no terms,
  abbreviations, or labels. Describe an identifier's behavior before naming it.
- Explain in prose, not formulas, arrow chains, pseudocode, or shorthand; a
  diagram may follow, never replace, a plain explanation.
- Surface only facts that affect the decision, never raw notes or reports.
- When the user corrects a premise, discard unapproved conclusions that depend
  on it and resume from the earliest affected stage.
- Show a change as a short "today / after" example with real values, not as
  internal IDs or requirement codes.
- If the user asks for context or does not understand, do not advance or open
  another fork: explain the concept plainly with a concrete example, then
  restate the same question more simply.

Keep a decision ledger of confirmed, assumed, open, rejected, and later-work
items; show it only at checkpoints or on request.

## Revising an existing scope

The baseline is the latest complete version of the spec, scope, or prior
result that the user supplied, referenced, or approved, recovered exactly from
the source or conversation history, not a summary; if none is accessible, ask
for it before claiming an exact comparison. Focus on the changes and what they
invalidate. Keep unchanged confirmed decisions unless a new detail contradicts
one, changes its consequences, or makes its evidence stale.

Keep a baseline-to-current change ledger of meaningful requirement and
contract changes: Added, Changed (old and new value), Removed, ignoring
wording, order, formatting, and section moves. An omitted baseline item is
removed only when the user removes it or an approved decision makes it
impossible.

## Repository and practice research

1. Read applicable `AGENTS.md` and repository documentation.
2. Inspect `git status --short --untracked-files=all`; existing changes are
   user-owned, not part of the task.
3. Find the owner, entry boundary, related modules, nearby production
   examples, helpers, contracts, tests, and focused validation tools; use
   recent history when it shows the pattern.
4. Distinguish strong local practice from weak, copied, inconsistent,
   outdated, or absent precedent.

- Spike: none, unless a concrete practice question can change the answer.
- Bounded: `repo-practice-review` with the intent and a focused question;
  `best-practice-review` only when local precedent is absent, weak,
  inconsistent, disputed, or creates a tradeoff that can change the scope or
  solution.
- Architectural: both; `best-practice-review` gets the intent, repository
  evidence, and repo-practice result and must say where local practice should
  be followed or challenged.

For standalone discovery, use `gpt-6.1-terra` high by default and `gpt-6.1-sol` high for novel,
cross-layer, high-risk, or difficult-to-validate questions, read-only, with no
recursive delegation. If a required role is unavailable, stop and name it;
never imitate it. A missing optional one does not block.

Then compare, as separately labeled evidence, what the repository does, what
strong general practice would do, where they agree, conflict, or leave no
precedent, and your reconciliation: the constraints and decisions that follow.

## Plan validation from the affected behavior

For Bounded and Architectural work, trace each affected behavior and supported
variant along the user-visible path, even for a one-line edit, to existing
tests, fixtures, Storybook stories, integration or e2e flows, and other
required artifacts. Keep an internal plan per scenario: existing evidence,
reuse/update/add, and the focused check that proves completion. A green suite
does not cover a scenario it lacks, such as a new variant missing from the
story matrix; extend the established feature matrix for it unasked.

Require `test-review` before scope completion when changed behavior involves
permissions or billing rules, a UI flow has multiple affected supported
variants, or coverage adequacy remains uncertain after inspection. Give it the
intent, affected behavior, coverage, and proposed checks, and ask for
omissions and the smallest sufficient validation, not new behavior. Reuse a
prior test-review when behavior, variants, and evidence are unchanged; main
may plan a clear local change alone. A Spike needs test-review only when
validation can change its conclusion.

No mandatory test levels or Cartesian products of unsupported combinations.
Add tests and artifacts only to prove requested behavior, a reachable
regression, or an established contract; otherwise record why existing evidence
suffices. Missing tooling is a gap, not proof a check is needless. Keep
commands, coverage notes, and rejected checks out of the scope unless their
exact form is required. Revisit the plan after a behavior or scope change and
in the final synthesis audit.

## Decompose oversized ideas

Before the interview, look for multiple independently valuable tasks
(separate user outcomes, independently deployable subsystems, unrelated
owners, a boundary too large to validate as one change). Identify the pieces,
their order, and the smallest useful first task; keep the rest as later work. In brainstorm mode, ask the user to choose the current
task (one interview question) and repeat affected research when the boundary
changes; in autopilot, choose it and say why.

## Define delivery slices

Separate user outcomes are separate tasks. Within one coherent task, define
slices only when implementation spans separable responsibilities that must
land in dependency order. Each states:

- `Outcome`: the independently understandable result it establishes;
- `Consumes`: exact behavior or contracts required from earlier slices;
- `Produces`: exact behavior or contracts later slices may rely on;
- `Depends on`: earlier slices, or `none`;
- `Validation`: observable evidence that the slice delivered its contract.

Describe contracts with exact approved names, values, formats, and
relationships, not 2-5 minute coding steps, files, helpers, or code shape
unless the user approved them as a real constraint. Omit slices for one small
coherent implementation.

## Brainstorm mode

### 1. Confirm understanding

The first response is only a short readback in the user's terms asking to
confirm or correct it: no repository inspection, substantive question, design
fork, or solution. Wait; a correction replaces the understanding.

### 2. Classify, research, and compare

Name the path and one concrete reason, then research; this is not an approval
gate, and the user may correct it at the next checkpoint. A Spike asks one
intent question only if necessary, returns findings and a recommendation, and
stops unless the user turns it into a build request. For Bounded or
Architectural work, show the comparison and wait for the user's reaction
before the interview, without solution options.

### 3. Interview one decision at a time

Interview even when the description seems detailed: one focused question per
message (this limits decisions, not explanation), no repeated settled facts.
Establish every relevant high-impact decision among:

- desired outcome and affected users;
- observable behavior and important current behavior to preserve;
- required scope, optional scope, and explicit exclusions;
- compatibility, data, permissions, rollout, failure, and operational
  constraints, only where the task touches them;
- observable evidence that would prove the task complete.

Ask only what the user can answer from the current message. Before asking
about a new mechanism, label, or tradeoff, explain it plainly, say what the
answer changes, give a concrete example or consequence, and recommend a
default when evidence or practice supports one. Never ask approval of an unexplained
term (a policy, marker, lifecycle, or opt-in), or "does that make sense?" in
place of the decision. Explain every linked premise in full; split across
turns only when a premise itself needs a user decision.

When several decisions are open at once, number each question, give it a short
title, and put the recommendation on its own line, phrased so a plain "yes"
accepts it. A reply such as "all good except 2" accepts the rest.

Ask another question only when its answer can change the goal, boundary,
approach, risk, or acceptance criteria, but always at least one to confirm the
highest-impact assumption. If an answer changes the boundary or the
comparison's basis, redo the affected research and show the corrected
comparison before options.

### 4. Compare approaches

Start from the closest existing analog in the repository: how the same problem
is already solved for a neighboring feature (for example the SQL version of an
HTTP change). Lead with repeating it, and describe the analog in one or two
plain sentences. Propose a new mechanism only when you can name why the analog
does not fit.

Generate approaches and filter them before showing any; Bounded work needs
only materially different directions, Architectural a broader
comparison when real alternatives exist. Viable means meeting the confirmed
goal, hard constraints, required preserved behavior, and the approved
boundary; drop rejected ideas and workarounds that widen the task, change
behavior that must stay, or add risk without benefit. Never manufacture
alternatives:

- Two or more viable: present those whose tradeoffs could change the decision
  (normally two or three), lead with a recommendation, and ask the user to
  choose, combine, or revise.
- One: say the constraints leave one direction and present only it; record
  discarded ideas under Rejected only when needed, never as choices.
- None: return to the affected research or interview decision; never silently
  weaken a confirmed constraint.

A direction the user already confirmed after seeing its evidence is chosen;
ask again only when that can still change it.

### 5. Approve the scope

Before the first approval, run a final synthesis audit: rebuild the ledger
from all user messages and annotations since invocation (after compaction,
recover them with history tools), not from summaries. The latest explicit
correction wins. Keep exact contract decisions such as numeric limits, literal
UI copy, filenames, permissions, error behavior, and complete field or item
lists.

For Bounded and Architectural work, then dispatch a read-only
`code-simplicity-review` on the draft Goal, Requirements, and Validation with
the research evidence. Ask which requirements describe a mechanism instead of
an outcome, which have no reachable failure without them, and which add most of
the size, each with a simpler alternative. Show the user a short minimal design
with its rough production and test size, and put each expensive requirement to
them as a numbered question with what dropping it would change. Never drop a
requirement yourself.

Before approval, map every confirmed decision to a canonical section or
Rejected (internally unless asked) and resolve contradictions. Research facts,
risks, and rejected ideas are not requirements merely because they surfaced.

- Bounded: one compact checkpoint with Goal, Requirements, Validation, and any
  necessary Output contract or open technical direction. No second checkpoint.
- Architectural: that checkpoint, then a technical direction checkpoint only
  when an unresolved implementation choice or hard technical constraint could
  materially change the result, with only the evidence it needs.

Never drop an exact decision for length; an Output contract may grow to the
detail implementation needs. A requirements change invalidates
dependent technical decisions. After approval, re-audit decisions changed
during it, build the canonical scope from the audited ledger, and return it,
after the revision summary when a baseline exists. No handoff prompt, no
implementation.

## Autopilot mode

Run every stage internally, including the viability filter, coverage plan,
required test-review, and final synthesis audit against the original user
messages. Answer interview questions from, in order, the user's words,
repository evidence, and explicit assumptions; re-run research when an answer
changes the boundary.

Between equally plausible interpretations, choose the smaller independently
useful scope. Best-practice guidance never invents product requirements. Mark
every answer the user or repository does not support as an assumption.

Return a report sized to the task: for Bounded or Architectural work, only
the findings and approach reasoning that justify the recommendation, then the
revision summary if a baseline exists, then the canonical scope; for a new scope, only the
canonical scope. The
recommendation is a working conclusion, not user approval.

## Revision summary

Show `Changes from previous version` from the audited change ledger, not a
prose diff: meaningful Added, Changed (`old -> new`), and Removed items with
exact names, values, limits, and contract details, omitting empty categories,
or say nothing material changed. The scope stays authoritative; the summary
holds no requirement missing from it.

## Canonical scope

The canonical scope is an implementation task specification, not a research
record. Always include Goal, Requirements, and Validation; add the others only
when their condition applies:

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

A requirement states an observable outcome, not a mechanism. How data is
matched, stored, locked, cached, batched, or kept consistent is a requirement
only when the user chose it, and then it goes in Implementation constraints.
Every requirement names the reachable scenario that would break without it.
Protection against a hypothetical race, an optimization, and a fix for an
existing bug next to the task go in Later work or a separate ticket unless the
user explicitly asks for them now.

- Goal: one outcome sentence.
- Requirements: user-visible behavior, permissions, compatibility rules,
  boundaries, and other accepted behavior.
- Validation: the agreed exact scenarios and artifacts, required test levels,
  permission matrices, and edge cases, not "add tests"; include stories or
  fixtures for a new supported variant, but no coverage table or
  justification of excluded test levels.
- Implementation constraints: only approved technical rules whose omission
  could cause a materially wrong solution. An owner, file, class, helper, or
  test location only when the user required it or it is part of the approved
  boundary.
- Out of scope: only explicit user decisions or credible ambiguities raised
  during the brainstorm.

Leave out repository evidence, practice commentary, rejected approaches,
generic risks, and untouched files or subsystems. State each decision once, in
the most specific section, apart from assumptions. The scope must be
reviewable without the discovery conversation.
