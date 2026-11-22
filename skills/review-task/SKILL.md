---
name: review-task
description: "Deep read-only audit of an implemented task, diff, branch, PR, or ticket: find credible risks, inspect tests, and run focused checks. Use only when the user writes `$review-task` (or `/review-task` in Claude Code) or asks for a deep review of an implementation. Not for implementing fixes."
---

# Review Task

## Claude Code runtime

If you are running in Claude Code rather than Codex, read
[`../develop-task/references/claude-code.md`](../develop-task/references/claude-code.md) before
anything else, including the entry task title. It maps Codex tools, model
names, task titles, and delegation to Claude Code; every gate and rule in this
skill still applies.

## Task title

At entry, read [`../chat-title/SKILL.md`](../chat-title/SKILL.md) and follow it with
the type `review`. `D` means the requested audit and report are complete, not that the implementation
has no findings or is merged.

## Core Contract

Audit one implemented task for credible correctness, requirement, testing,
runtime, simplicity, and repository-practice issues. In standalone mode you own
orchestration, evidence collection, validation selection, and the final risk
report.

Stay read-only: do not fix product code, keep test changes, commit, push, edit
PRs, update Linear, or manage lifecycle state; report issues for the user to
delegate.

`$review-task` authorizes read-only delegation to `$diff-review`, the
specialists below, the finding verifiers, and the visual-evidence inspector; do
not wait for a separate request for subagents.

Avoid persistent repository edits; probe with temporary files outside the
repository, one-off snippets, Browser/Playwright, or a harness in dry-run form.
Ask before any expensive, destructive, or externally mutating action, except a
narrow repository-approved trigger a stated validation bar needs.

## Embedded development audit

When explicitly combined with `$develop-task` for one implementation task, read
[`../develop-task/references/composed-workflows.md`](../develop-task/references/composed-workflows.md).
Main applies this audit in the shared run with develop-task's backend, matrix,
ceiling, requirements, coverage plan, and usage accounting: no standalone model
defaults, second orchestrator, or unrequested brainstorm.

The independent final postflight reviewer performs the audit from a fresh
packet with the original requirements, current diff, base revision, and
validation evidence, using supported shared roles rather than a separate
diff-review backend. Develop-task's authorized writer owns
fixes and its gate owns approval. Main triages findings under the shared
correction budget; the audit has no fix loop or completion/lifecycle authority.

## Review Depth

Choose from the user's wording:
- `standard` (default): the workflow below with focused existing checks.
- `deep`: on request for a very detailed review or runtime/preview checks, or for risky changes; add runtime smoke checks and temporary probes when useful.
- `audit`: only on explicit request; be maximally thorough, but ask before long-running suites, environment setup, or broad CI-equivalent work.

## Specialist Model Routing

These defaults apply only to standalone review. Give every specialist an
explicit callable model ID and effort, and `fork_turns: "none"` or a positive
bounded history with a self-contained packet.

- `standard`: `gpt-6.1-terra` high; `deep`: `gpt-6.2-sol` high; `audit`:
  `gpt-6.2-sol` xhigh by default.
- `gpt-6.2-sol` max only when several critical risks combine, failure is
  especially costly or hard to validate, or a lower Sol tier made a conceptual
  mistake.
- Runtime, preview, and visual probes (rendered UI, screenshots, Playwright)
  use `gpt-6.1-terra` high at any depth; the depth's model judges defects.
- Finding verifiers and the visual-evidence inspector judge defects, so they
  use the depth's model and effort.

Raise the route when repository evidence is riskier than the depth word. If a
route is unavailable, use an equivalent-or-stronger one or check manually and
report the delegation gap; never silently downgrade.

## Workflow

1. Identify the target: local diff, branch, commits, PR, ticket, or patch. Default to the current diff; ask only when several targets are equally plausible.
2. Read repository instructions such as `AGENTS.md` and `git status --short --untracked-files=all`.
3. Reconstruct intent from the request, ticket, PR, commits, OpenSpec, and acceptance criteria. Report missing business requirements as uncertainty; do not invent them.
4. Map changed files, subsystems, contracts, state flow, persistence, runtime paths, and likely failure modes.
5. Collect existing validation evidence first. Run only missing focused validation that can change confidence, preferring narrow checks or temporary probes over broad suites.
6. Delegate when useful: `$diff-review` (fresh diff pass), `repo-practice-review` (local conventions and helpers), `best-practice-review` (engineering risks, weak precedent), `test-review` (coverage and e2e/smoke strategy), `code-simplicity-review` (scope creep, simpler approaches). If agents are technically unavailable, do their checks manually and say so.
7. Correlate all evidence yourself; specialist output is evidence, not the verdict. The result is a list of candidate findings.
8. Verify the candidates (Finding verification) before any of them reaches the report.

## Coverage and baseline verification

Check coverage of the requested behavior across relevant layers, not only the
tests and files the implementation chose; trace new supported variants into
story and fixture matrices, permission tests, and runtime flows. A green suite
or approved scope does not prove an omitted scenario. Report a missing artifact
only when the requested behavior or demonstrated repository practice requires
it.

Compare each credible finding with the base revision when available. Tie scope
to a requirement or preserved contract, not severity or file proximity. A
pre-existing issue that stops a requirement from holding is not automatically
out of scope; other out-of-scope risks are follow-up work, not defects or a
reason to broaden the patch. If origin or required behavior is unclear, report
the uncertainty instead of guessing or proposing new product behavior.

## Passed Check Reuse

Cite a passed test, CI job, or command instead of rerunning it when it ran on
the same commit, head, or diff after the relevant changes; its exact name and
result are known; its scope covers the touched code or risk; and no relevant
dependency, environment, configuration, or generated artifact changed since.

Rerun or supplement when it is stale, failed, flaky, skipped, cancelled, or of
unknown scope; ran on the base, an older commit, or before relevant changes;
does not cover the risk under review or a new review hypothesis; or the user
asks.

## Stated Validation Bars

A concrete bar in the requirements or target, such as `10/10 focused reruns`,
is part of the contract. Meet it when technically available.

- Count existing passes only when they match the commit, test target, environment, and command intent; run missing repetitions when safe.
- Stop and report a confirmed finding on any failed repetition.
- For a repository-approved external trigger, such as a PR comment starting focused e2e, do only that; do not edit PR metadata or lifecycle state.
- If credentials, environment, runner access, time, or safety block the bar, report a validation gap naming the blocker, not "weaker evidence".
- One green run never replaces a repeated-run bar unless the requirement owner relaxed it.

## Runtime And Preview Verification

With a preview URL, deployed build, or running local environment, safely test
high-risk UI/runtime behavior. UI: Browser/Playwright smoke checks of concrete
flows (visible state, network/runtime errors, navigation, loading/empty/error
states, responsive behavior when relevant); temporary probes only when they add
evidence beyond manual inspection or existing e2e. Backend: focused API,
service, migration, or integration checks via repository commands. Mutate
production-like data only where explicitly safe for testing.

In `standalone` mode, capture these checks as
[`../visual-evidence/SKILL.md`](../visual-evidence/SKILL.md) describes, including its
inspection of every screenshot and video, and give the developer the files in the chat;
this review stays read-only, so it posts nothing to the PR or the ticket. What the
inspection finds wrong is a finding.

## Review Checklist

Look for happy-path-only behavior; missing null, empty, permission,
concurrency, retry, pagination, timezone, migration, rollback, or compatibility
handling; stale state, lifecycle, cache, event, subscription, or async races;
data loss, persistence drift, schema mismatch, or unsafe migrations; UI
workflow gaps, broken loading/error/empty states, inaccessible controls, or
layout regressions; and security, authorization, tenant isolation, secret exposure,
or unsafe external calls.

Also check, yourself when no specialist covers it: mismatch with stated requirements or
acceptance criteria; tests that overfit the implementation, miss the actual regression,
duplicate coverage, or are brittle; unnecessary abstractions, scope expansion, dead code,
or custom logic where repository helpers or libraries exist; and deviation from
repository practice without a justified reason.

## Evidence Standards

Be strict, not noisy: a finding needs a plausible failure path and concrete
evidence from code, requirements, tests, runtime, or a reproducible check.
Separate confirmed findings, credible risks needing owner judgment, validation
gaps, and open requirements questions. Do not bury important issues in a long
summary or present style opinions as blocking defects.

Not a finding:

- a problem that was there before the change, unless the change makes it
  reachable or worse, or it stops a stated requirement from holding;
- code that looks wrong but is correct once its callers and data are read;
- what a linter, typecheck, or existing test catches, unless that check did not run;
- a style, naming, or structure preference with no failure behind it;
- a failure that needs an input or state nothing can produce;
- a missing test or guard for behavior nobody asked for.

Explain each finding plainly: one finding per item, what happens today and what
goes wrong, with a concrete example, in the user's vocabulary rather than internal
IDs. When suggesting a simpler direction, start from how the repository already
solves the same problem elsewhere and say why it fits or does not. When the user
does not understand, explain the same finding again more simply before moving on.

## Finding verification

In `standalone` mode no candidate finding reaches the report until a fresh agent
has tried to disprove it. A reviewer asked to find problems always finds some;
this step removes the ones that are not real. In `embedded` mode skip it: the
gate and main's challenges do that work.

Give each candidate a severity (see Output), then start fresh verifiers with no
conversation history, in parallel when the tool layer allows:

- each `P0` or `P1` candidate gets its own verifier;
- all `P2` candidates share one verifier, or one per area when they touch
  unrelated parts of the code;
- `P3` candidates get none: keep one only when you can point to the exact line
  and the wrong result yourself, and drop the rest.

Give a verifier only this, for each of its candidates:

- the claim in one or two sentences: the input or state, and what goes wrong;
- the requirement or contract it would break, with its source;
- the diff, the base revision, and the paths involved.

Do not give it the severity, the reasoning behind a claim, candidates that belong
to another verifier, or your opinion: a verifier that sees a verdict tends to
repeat it.

A verifier works under this review's own contract: no edits in the repository,
and probes in temporary files outside it. When a check on the base needs a base
checkout, main prepares a disposable one outside the repository and removes it
afterward. A verifier that cannot run its check returns `could not check` with
the command, and main runs it.

Ask the verifier to try to prove each claim wrong and to return one result per
claim, with evidence:

- `confirmed`: it reproduced the problem or traced the exact failing path. It
  names the command, test, probe, or request with its output, or the path with
  file and line. It also says how the base revision behaves, from the same check
  on the base or from the base code: the problem is new, older and made reachable
  or worse by the change, or older and unchanged.
- `did not hold up`: the claim is wrong, and why.
- `needs a decision`: the code does what the claim says, and whether that is
  wrong depends on intent the requirements do not settle.
- `could not check`: what blocked the check and what would settle it.

Prefer running a check to reading the code: a focused test, a temporary probe,
or a request against the preview. Reading alone confirms only what the code
shows directly, such as a missing branch or a wrong condition.

Then place each candidate in the report:

- `confirmed`, and new or made reachable or worse by the change: Findings;
- `confirmed`, older and unchanged: Details, as an older problem. It is a
  follow-up and never a reason to change this PR. The exception is an older
  problem that stops a stated requirement from holding: that is a finding;
- `needs a decision`: Needs from you;
- `did not hold up`: Details, as a dropped claim with the reason;
- `could not check`: Checked and not checked, under Not checked.

Do not overrule a verifier with your own opinion; when you disagree, give it new
evidence once, and its second answer stands. A defect the visual-evidence
inspector shows in an image needs no verifier unless it depends on behavior the
image cannot show. If verifier agents are unavailable, verify each candidate
yourself the same way, starting from the claim alone, and say so under Details.

## Report Mode

Use `standalone` only when the end user's active request directly invokes
`$review-task` or asks for this review as the deliverable and you own the final
response; an implementation step,
self-review, gate, or input to another agent or workflow is `embedded`. An
explicit mode from the user or calling workflow wins; never ask. `embedded`
reports only actionable findings, validation evidence and gaps, delegation,
and the verdict.

## Output

In `standalone` mode, write the report from this template. Keep every heading and
field in this order and write `none` where a section has nothing. Before sending,
check that no heading or field is missing.

```markdown
### What this PR does
<what a user or a caller sees: how it was and how it is now, with one real example>

### Why it is needed
<the problem or request behind it, and who ran into it>

### How it works
<the path in order: what starts it, what the code now does at each step, and where the result ends up>

**Not obvious:** <what a reader would not guess: a constraint, an order, a special case, a trade-off; or none>

### Verdict
<ready | ready after fixes | not ready | cannot tell>: <the reason and the remaining risk, in one or two sentences>

### Needs from you
<nothing, or each decision as a numbered question: what the code does, the options, and a recommendation that a plain "yes" accepts>

### Findings
#### <P0 | P1 | P2 | P3> — <what goes wrong, in plain words>
- **What happens** — <the steps or input, what the user or caller gets, and what they should get>
- **Why it matters** — <who is affected and how badly>
- **Where and since when** — <file and line; new in this PR, older and made reachable or worse by it, or older and stops a named requirement from holding>
- **How it was confirmed** — <the check that was run and its result, or the code path that was traced>
- **Fix direction** — <one or two sentences, not a full plan unless asked>

### Checked and not checked
- **Run in this review:** <checks and their results>
- **Reused:** <passed checks cited, with commit and result>
- **Not checked:** <what, why, and what would check it>

### Details
- **Dropped claims:** <each claim that verification rejected and why, one line each>
- **Older problems:** <each problem that was there before this PR and where, one line each; follow-ups only>
- **How the review ran:** <agents used with model and effort, or the manual fallback>
```

Severity is `P0` critical, `P1` blocks the merge, `P2` should be fixed, or `P3`
minor; order findings by it. The verdict follows from them: `not ready` with any
`P0` or `P1`, `ready after fixes` with `P2` findings and nothing higher, `ready`
with no findings or only `P3`, and `cannot tell` when a missing requirement or an
unchecked risk decides the answer. With no findings, write `none` under Findings
and still fill in the other sections.

The first three sections are what the developer reads to remember the task, so
write them for someone who knows the product but has not seen this code and does
not remember the ticket:

- Start from what a user or caller could not do, or saw, before the change, then
  what they see now. Give one example with real values: a screen, a request, a
  setting.
- In How it works, walk the path once, in order. Name at most the three or four
  places in the code that matter, and say what each does before giving its name.
- Under Not obvious, put what would surprise a careful reader. If nothing would,
  write `none` rather than restating the summary.
- Use the words of the ticket and the UI. Explain any other term in the same
  sentence, with no internal IDs, file lists, or review jargon.
- Cut a sentence that would fit a report about another PR.

Base these sections on the diff, ticket, and PR; label anything undocumented as an
inference, and do not invent product intent.
