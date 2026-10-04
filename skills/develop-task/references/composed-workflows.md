# Explicitly composed workflows

Read this reference only when the user requests implementation through
develop-task together with brainstorm-task, review-task, or both. Skill names
inside quoted examples, source material, or a request to discuss the skills
are not invocations. An explicit sequence in natural language also qualifies;
the names need not be adjacent or in a particular order.

## Select only the requested phases

| Explicit skills for one implementation task | Discovery | Final audit |
| --- | --- | --- |
| develop-task | Existing develop-task framing | Mandatory postflight |
| brainstorm-task + develop-task | Brainstorm before preflight | Mandatory postflight |
| develop-task + review-task | Existing requirements; no brainstorm | Review-task checks in final postflight |
| brainstorm-task + develop-task + review-task | Brainstorm before preflight | Review-task checks in final postflight |

Standalone brainstorm remains read-only discovery; standalone review remains
a read-only audit with no automatic fixes. Without an implementation request,
combining their names does not authorize development or persistence. Do not
activate an omitted skill to complete the set.

## One coordinator and one engineering run

Main reads each explicitly selected skill completely and applies its relevant
phase. It does not dispatch a nested orchestrator or create a second run.
Resolve the develop-task backend, matrix, and ceiling before the first job,
including discovery specialists. Use the same runner manifest, role contracts,
fresh-context packets, writer ownership, and cumulative usage for all phases.
Read the runner reference before any runner job, not only before preflight.

Route a discovery specialist's concrete question through develop-task's
factual-lookup or decision-determining rules using a preliminary profile. New
evidence may revise that profile before preflight. Embedded skills must not
use their standalone model defaults, bypass a ceiling, switch backend, or
finalize the run after their phase. In runner mode, use supported review roles,
not new `brainstorm-task` or `review-task` runner roles. Before initial preflight,
discovery jobs use contract revision 1 and no approving-preflight link.

An explicitly selected outer workflow, such as develop-please, retains its
authorized ticket, branch, PR, CI, preview, and reporting responsibilities.
Discovery and audit phases are not outer lifecycle controllers. Main dispatches
engineering jobs and passes results or persistence requests to that controller.

## Discovery and scope persistence

Run the selected brainstorm mode, including its behavior-based coverage plan.
Interactive discovery keeps its one-question interview and required approvals.
Explicit autopilot does not wait for routine scope approval. Its recommendation
is an agent conclusion, not a fabricated developer decision. Continue only
within the user's implementation request and evidence-supported behavior;
material unresolved product choices or conflicting requirements stop affected
implementation. A Spike ends with findings unless implementation is separately
authorized and its requirements are established.

Before implementation, persist the complete canonical scope, not merely its
change summary. The combined implementation request authorizes this narrow
scope persistence, subject to explicit user limits and outer lifecycle rules:

- Use the exact existing task ticket when known and writable. Update a clearly
  identified scope section or linked task document; preserve original source
  requirements, comments, unrelated content, and existing confirmed decisions.
- If no suitable ticket is available, choose the repository's established
  specification location, or a small task-specific file when no convention
  exists. Never overwrite an unrelated or user-modified file.
- Do not create a ticket solely to store the scope without user authorization.
  If an optional ticket update is unavailable, save to a file and disclose the
  fallback. If updating that ticket is an explicit required deliverable, keep
  the gap unresolved rather than declaring the file a substitute.

Keep one authoritative scope location and its current revision/source reference
in every later packet. Distinguish exact user requirements, evidence-supported
repository contracts, and autopilot assumptions. Stable requirement IDs and
confirmed amendments follow Requirements Fidelity; a reviewer or an assumption
cannot become an explicit developer decision. Technical fix contracts and
coverage-plan refinements do not amend product requirements. Synchronize actual
user amendments without rewriting historical job snapshots.

Without brainstorm, use the existing requirements and amendments normally.
Do not invent another scope document or approval ceremony merely because
review-task was also requested. Do not duplicate a full canonical scope in
routine progress messages after saving it; give its location and meaningful
changes unless the user requests the full text.

## Final audit and correction decisions

When review-task is selected, main applies its evidence collection, focused
validation, passed-check reuse, baseline comparison, and scope assessment in
embedded mode after implementation and relevant available checks. Give a fresh
independent postflight reviewer the complete source requirements, saved scope,
coverage plan, base revision, current diff/head, validation evidence, and
review-task audit instructions. That reviewer performs the independent audit
and returns the normal postflight decision plus the audit findings and gaps.
Do not replace this with main's self-review or treat an earlier shallow gate
approval as having performed the requested audit.

Use that one final postflight as the approval gate, not a second independent
review/fix loop. Main dispatches additional read-only specialists only for
concrete questions and returns their reports to the gate. Reuse checks that
cover the current behavior and head; do not rerun full suites for every finding.
If required preview or CI evidence becomes available only after publication,
the outer controller supplies it before final completion. Publication still
requires current pre-publication postflight approval. Any later implementation
mutation invalidates approval and follows the same fix rules and shared budget.

For each finding, establish scope and origin independently:

- Auto-fix a confirmed in-scope defect, missing requirement, or required
  coverage/artifact omission. Preserve product behavior and use the existing
  mechanical/substantive/replan classification before resuming a writer.
- A pre-existing defect belongs to this task only when it prevents a stated
  requirement or proven preserved contract from holding on the affected path.
  Fix it only within the authorized boundary; otherwise request a decision.
- Leave unrelated pre-existing issues and nonessential improvements as
  follow-up observations. Being old does not excuse a required-contract
  failure; being severe does not itself authorize unrelated remediation.
- A finding requiring new product behavior or wider scope needs a user
  decision. Do not silently amend the saved scope to justify a fix.

Main records accepted, declined, and deferred findings with evidence. A
contested blocker must return to the reviewer for adjudication; main cannot
waive it. Optional comments are not automatic fix requests. A missing supported
story may be a coverage obligation even if no one explicitly named that file.

Follow develop-task's Bounded Review Loop across audit, postflight, fixes,
contract revisions, and post-publication checks. Do not grant embedded review
its own additional three attempts. Completion requires current approval and
all authorized outer completion gates; otherwise report the exact decision or
blocker with work preserved.
