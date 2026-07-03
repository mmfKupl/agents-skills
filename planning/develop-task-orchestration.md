# Develop Task Orchestration Notes

## Current Decision

`develop-task` is the main orchestration skill for engineering execution.
It coordinates context gathering, OpenSpec when warranted, specialist reviews,
implementation, validation, and the postflight fix loop.

`develop-task` should not own business-requirements discovery. Business
requirements, acceptance criteria, and product clarification should later live
in a separate skill with its own agents.

Current MVP:
- skills: `develop-task`, `openspec-workflow`, `diff-review`;
- core/coordination agents: `preflight-review`, `postflight-review`,
  `openspec-steward`;
- generalist specialists: `repo-practice-review`, `best-practice-review`,
  `test-review`, `code-simplicity-review`;
- domain specialists are deferred.

## Skills

### develop-task

Main engineering workflow orchestrator.

Responsibilities:
- identify the technical task boundary;
- inspect repository policy and dirty-tree state;
- choose which specialist agents are needed;
- coordinate OpenSpec usage for complex tasks while skipping it for small
  obvious work;
- implement code changes through the main agent only;
- run focused validation;
- coordinate post-implementation review loops;
- when committing repository changes, split them into logical commits instead
  of one broad commit;
- when repository work reaches an approved final state, prepare a pull request
  with the resulting changes;
- report final state.

### openspec-workflow

OpenSpec integration workflow.

Responsibilities:
- detect whether `openspec/` exists in the repository;
- initialize a local ignored OpenSpec workspace when explicitly requested and
  absent;
- prefer `.git/info/exclude` for `/openspec/` so pilot artifacts stay local by
  default;
- read relevant specs and changes;
- create and update OpenSpec change artifacts;
- validate OpenSpec artifacts when the CLI is available;
- use OpenSpec by default for large, complex, ambiguous, cross-layer, or
  durable-behavior tasks;
- skip OpenSpec for small obvious changes where the code, tests, and commit
  message carry enough intent.

`openspec-workflow` owns the procedural rules for using OpenSpec. The
`openspec-steward` agent applies those rules during a concrete task.

### diff-review

Fresh independent review of the current local diff.

Responsibilities:
- review the diff with minimal prior context;
- look for correctness issues, missing tests, scope creep, overengineering,
  and simpler alternatives;
- support standalone review requests and review gates before commit, push, or
  resolving review threads.

## Agents

### preflight-review

Read-only pre-implementation architecture and boundary reviewer.

Use before implementation to validate:
- problem framing;
- owner and entry boundary;
- smallest correct surface;
- canonical path;
- major risks;
- validation plan;
- blockers before editing.

### postflight-review

Read-only post-implementation reviewer.

Use after implementation to validate:
- correctness;
- architecture fit;
- missing tests;
- validation gaps;
- simpler alternatives;
- approval or blocking findings.

### repo-practice-review

Read-only repository-practice reviewer.

Can be used before or after implementation.

Use to check:
- existing repository patterns and conventions;
- naming and ownership conventions;
- nearby implementations;
- local helper APIs and tools;
- whether the change follows established practice;
- whether the implementation introduces pattern drift;
- whether the repository lacks a clear local pattern or the local pattern looks
  outdated, weak, or inconsistent.

This agent must ground its advice in repository evidence. It should avoid
generic best-practice claims unless it is explicitly contrasting them with
repository practice.

### best-practice-review

Read-only general engineering best-practice reviewer.

Can be used before or after implementation.

Use to check:
- how similar problems are commonly solved outside this repository;
- whether the proposed approach is maintainable, robust, idiomatic, and
  appropriately scoped;
- whether the repository pattern should be followed, adapted, or challenged;
- whether missing or weak repository precedent justifies introducing a better
  pattern;
- what risks come with introducing a new local pattern.

This agent must avoid claiming repository conventions without repository
evidence. It provides general engineering guidance; the requesting core gate
decides how to reconcile that guidance with local repository practice.

### test-review

Read-only test strategy and test-quality reviewer.

Use flexibly before or after implementation. It should not try to review every
test concern every time; it should focus on the test risks relevant to the
current change.

Use to check:
- which existing tests are relevant;
- what focused validation command should be run;
- whether new or updated tests are justified;
- whether tests prove behavior instead of implementation details;
- whether test style follows nearby patterns;
- whether important edge cases are missing;
- whether the proposed tests are simple enough for the behavior being proved;
- whether the change is low-risk enough to avoid adding tests;
- whether complex frontend behavior needs e2e, integration, screenshot, or
  smoke validation instead of only unit tests.

This agent should avoid asking for tests on everything. It should prefer the
smallest behavior-focused test or validation that proves the change. It should
flag overcomplicated, brittle, implementation-detail-heavy, or broad tests.

### code-simplicity-review

Read-only simplicity, reliability, and scope reviewer.

Can be used before or after implementation.

Use to check:
- whether the problem can be solved closer to the boundary;
- whether the patch is too broad;
- whether new abstractions are justified;
- whether a simpler or more reliable approach exists;
- whether the code stays within the requested scope;
- whether the repository already has code-quality tools that should be used;
- whether unrelated behavior or files were changed outside the task context;
- whether code was added for its own sake rather than to solve the requested
  problem;
- whether existing repository helpers, utilities, libraries, or stable external
  libraries can replace custom code;
- whether adding a small proven dependency would be safer than hand-rolling
  complex logic, when dependency policy allows it.

This agent should be strict about scope control. It should challenge unrelated
changes, speculative branches, unused extension points, broad compatibility
layers, and custom implementations of solved problems.

### openspec-steward

Core-level OpenSpec-focused agent.

Can be called by:
- `develop-task` when a task explicitly opts into OpenSpec, needs OpenSpec
  setup, or is large/complex enough that OpenSpec should be used by default;
- `preflight-review` when planning should consult or create OpenSpec change
  artifacts;
- `postflight-review` when a completed diff must be checked against OpenSpec.

`preflight-review` and `postflight-review` may call `openspec-steward` in
read-only mode to inspect existing OpenSpec specs, check whether OpenSpec is
needed, or review drift. Write-mode OpenSpec edits are allowed only when
`develop-task` has established that the task uses OpenSpec or the user has
explicitly requested OpenSpec changes.

Goal:
- avoid many narrow OpenSpec agents;
- let one agent inspect OpenSpec state, make or propose change artifact
  updates, and review drift between implementation and OpenSpec artifacts;
- keep the main agent from spending excessive context on OpenSpec mechanics.

Responsibilities:
- inspect existing OpenSpec layout and relevant specs;
- initialize a local ignored OpenSpec workspace when explicitly asked and when
  the repository does not already use OpenSpec;
- make scoped edits under `openspec/` for proposal, design, tasks, and delta
  specs when the task opts into OpenSpec;
- add `/openspec/` to `.git/info/exclude` when initializing local pilot
  artifacts, unless the user explicitly wants repository-tracked OpenSpec;
- decide whether an OpenSpec change is needed when asked;
- propose or review `proposal.md`, `design.md`, `tasks.md`, and delta specs;
- identify stale or missing OpenSpec tasks after implementation;
- recommend validation or archive steps;
- avoid editing product code or normal tests.

Default write scope:
- may edit OpenSpec artifacts and local git exclude files when the task uses
  OpenSpec;
- must not edit application code;
- must not commit, push, or archive changes without explicit user approval.

OpenSpec default-use heuristic:
- use for large, complex, ambiguous, cross-layer, high-risk, or durable behavior
  changes;
- use when implementation intent is likely to be lost across chat context,
  review cycles, or follow-up sessions;
- skip for small, obvious, local changes where the code, tests, and commit
  message are sufficient.

## Delegation Model

Logical routing belongs to the review layer:
- `preflight-review` decides which generalist specialists are useful before
  implementation;
- `postflight-review` decides which generalist specialists are useful after the
  diff exists;
- `openspec-steward` can be called directly by `develop-task` or by either core
  gate.

Technical spawning may still be performed by the root/main agent when the
current Codex surface or `agents.max_depth` setting does not allow nested
subagent spawning. In that fallback, the core gate returns an explicit
delegation request and `develop-task` spawns the requested specialist "on
behalf of" the gate.

When a core gate asks for a specialist through a delegation request,
`develop-task` must:
- pass the specialist prompt verbatim;
- avoid expanding, narrowing, or rewriting the specialist request;
- avoid independently interpreting or adjudicating the specialist result;
- return the specialist result to the requesting core gate;
- act only on the final recommendation from the requesting core gate.

`develop-task` may challenge a core gate decision with concrete evidence, but
must not silently override it. Challenge evidence may include repository code,
diff facts, command results, validation constraints, user constraints, or
specialist output the gate appears to have misinterpreted. The same core gate
owns the updated decision.

Gate challenge loops are bounded to 5 iterations. If `develop-task` and the
core gate cannot resolve a blocker, classification, scope question, or
validation dispute after 5 iterations, `develop-task` must stop and ask the
user for a decision.

Do not encode all specialist routing directly into `develop-task`; keep
`develop-task` responsible for phase orchestration, not detailed review
decomposition.

Delegation requests should state whether the specialist result is blocking or
advisory for the current gate decision.

Generalist specialists must not recursively delegate to other agents. Further
delegation goes through the requesting core gate.

When specialist outputs conflict, the requesting core gate must resolve the
conflict explicitly. It should explain whether to follow repository practice,
depart from repository practice, take a transitional/local fix, or stop for a
user decision.

If a task lacks business or product requirements, the preflight gate must stop
and report that requirements discovery is needed. It must not invent product
behavior.

Postflight reviews should receive the review cycle number and the previous
postflight findings/fixes so they do not repeat optional feedback or lose track
of unresolved blocking issues.

Postflight reviews must audit diff scope: whether files, behavior, exports,
tests, or generated artifacts changed outside the task boundary. The core gate
owns classification of out-of-scope changes as blocking, recommended, or
acceptable.

## Commit Policy

For implementation work in a git repository, `develop-task` should normally end
with committed changes and a pull request unless the user explicitly asks to
stop with local changes only.

When committing:
- split changes into logical commits instead of one broad commit;
- keep each commit independently understandable and reviewable;
- avoid mixing OpenSpec/setup artifacts, product implementation, tests, and
  mechanical cleanup when they can be cleanly separated;
- do not commit optional or unresolved review findings unless the user decides
  to proceed;
- follow the configured Codex commit-message rules.

## Pull Request Policy

For repository implementation work, `develop-task` should create or update a PR
after:
- implementation is complete;
- focused validation has run or skipped checks are explicitly documented;
- `postflight-review` has approved the diff, or the user explicitly decides to
  proceed despite remaining findings;
- commits have been split into logical units.

Default PR behavior:
- create a branch when needed;
- commit logical chunks;
- push the branch;
- open a draft PR by default unless the user asks for a ready PR;
- include the problem, fix summary, validation, review-gate results, OpenSpec
  change reference when relevant, and known limitations in the PR body.

Do not create a PR when:
- the request is analysis-only;
- no repository files changed;
- the task is blocked;
- postflight has unresolved blocking findings and the user has not explicitly
  decided to proceed;
- dirty-tree conflicts make it unsafe to isolate the task changes;
- the user asks to keep the work local.

## Open Questions

### Specialist risk agents

Deferred potential agents:
- `contract-boundary-review`;
- `security-permissions-review`;
- `state-runtime-review`;
- `persistence-migration-review`;
- `ui-workflow-review`;
- `datasource-runtime-review`.

Decision:
- do not implement domain specialists in the MVP;
- do not replace `preflight-review` or `postflight-review` with domain
  specialists yet;
- keep `preflight-review` and `postflight-review` as broad default gates;
- use the generalist specialists first;
- revisit domain specialists only after repeated real tasks show clear value.

## Deferred

Workflow details are intentionally not finalized yet. The next discussion
should decide how `develop-task` routes between the core review gates,
generalist specialists, OpenSpec, and future domain specialists.
