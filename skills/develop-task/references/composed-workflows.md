# Explicitly composed workflows

Read this reference only when the user requests implementation through
develop-task together with brainstorm-task. Skill names
inside quoted examples, source material, or a request to discuss the skills
are not invocations. An explicit sequence in natural language also qualifies;
the names need not be adjacent or in a particular order.

## Select only the requested phases

| Explicit skills for one implementation task | Discovery |
| --- | --- |
| develop-task | Existing develop-task framing |
| brainstorm-task + develop-task | Brainstorm before preflight |

Every develop-task run ends with a full review of its own, its Final Review, so
naming review-task next to it selects nothing. Standalone brainstorm remains
read-only discovery; standalone review remains a read-only audit with no
automatic fixes. Without an implementation request, combining their names does
not authorize development or persistence. Do not activate an omitted skill to
complete the set.

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
not a new `brainstorm-task` runner role. Before initial preflight,
discovery jobs use contract revision 1 and no approving-preflight link.

An explicitly selected outer workflow, such as develop-please, retains its
authorized ticket, branch, PR, CI, preview, and reporting responsibilities.
A discovery phase is not an outer lifecycle controller. Main dispatches
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
Do not duplicate a full canonical scope in
routine progress messages after saving it; give its location and meaningful
changes unless the user requests the full text.
