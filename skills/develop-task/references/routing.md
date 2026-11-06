# Routing and implementation slicing

Read this before preflight for a preliminary Deep, Critical, or Exceptional task,
when the source scope has Delivery slices, and before any model promotion or
diagnosis job. Preflight names the exact route; this explains how it is chosen.

## Critical and Exceptional

Critical indicators include security, authentication, permissions, billing,
persistence, migrations, destructive behavior, concurrency, public contracts,
and low-validatability changes.

Exceptional requires concrete evidence for at least one of these conditions:

- the task combines several critical contracts, lacks a reliable local pattern
  for the core decision, and is difficult to validate or roll back;
- the key decision requires novel architecture across several tightly coupled
  subsystems;
- `gpt-6.1-sol` high or xhigh already made a conceptual error or could not
  produce an approvable contract from sufficient context.

Do not select Exceptional for a single familiar authentication, permission,
billing, migration, concurrency, or public-contract change with an established
pattern. Record the evidence that justified every Exceptional route.

## Slices and routes

Use one implementation job by default for Fast and Standard work. Do not split
a small coherent change merely to create more agents.

Before preflight, identify whether a preliminary Deep, Critical, or Exceptional
task contains multiple independently bounded layers or responsibilities. When
one worker packet would combine several such areas, propose ordered
implementation slices. Typical boundaries are a migration or persistence
contract, backend enforcement, API or token contracts, frontend behavior, and
integration coverage. Slice by responsibility and dependency, not by arbitrary
file count.

When an approved source scope already contains Delivery slices, use them as the
starting decomposition. Preserve their exact `Consumes`, `Produces`, `Depends
on`, and `Validation` contracts while resolving concrete owners and paths from
the current repository. Preflight may revise the decomposition only when it
cites repository evidence that the approved handoff is impossible or unsafe;
do not silently merge, reorder, or reinterpret an approved slice contract.

Require preflight to approve either one implementation job or an exact ordered
slice plan. Every slice must state its responsibility and owned paths,
dependencies, consumed and produced behavior or interfaces, acceptance
evidence, focused validation, and replan triggers. All approved slices remain
under the same contract revision and use separate fresh runner jobs. Keep one
worktree writer active at a time, inspect each result and diff before starting
the next slice, and run
postflight on the combined implementation after all slices finish. A slice
that invalidates the approved boundary, ordering, behavior, or critical
contract stops the sequence and returns to fresh preflight.

Use `gpt-6.1-terra` medium for confirmed Fast implementation and high for
confirmed Standard implementation. Fast postflight uses `gpt-6.1-sol` low;
Standard postflight uses `gpt-6.1-sol` medium. A conceptual failure despite
sufficient context, newly ambiguous requirements, or novel coupled behavior
requires fresh preflight to reassess the affected scope and its profile. When
that preflight keeps the Standard profile, the next writer may use Terra xhigh;
move implementation to Sol only after Terra xhigh also fails conceptually or
the profile changes. Ordinary lint, type, formatting, build, or test
failures alone do not justify changing models. Keep the Standard postflight
floor at `gpt-6.1-sol` medium while the task remains Standard.

For Deep implementation, use `gpt-6.1-sol` high. A conceptual failure, novel
architecture without a strong local precedent, or several inseparable coupled
layers may require a fresh preflight and Exceptional routing for the affected
slice. A lint, type, formatting, build, or ordinary test failure alone is not a
promotion reason.

For a visual or prose slice in a Deep, Critical, or Exceptional plan, use
`gpt-6.1-terra` high. Use Terra xhigh only for a Critical visual slice that
combines several concrete factors from the next paragraph. A visual slice that
changes a critical contract or carries the exceptional decision is not a
visual slice for routing; route it like any other slice.

For Critical implementation, keep a bounded slice with an established
repository pattern on `gpt-6.1-sol` high. Use Sol xhigh only when the exact slice
combines several concrete factors: security/auth reasoning, concurrency, complex
migration, costly public-contract change, difficult validation or rollback,
or a prior conceptual failure by Sol high. Reserve Sol max for quality-first
work after a lower Sol tier fails conceptually; do not apply it automatically.

For Exceptional implementation, start ordinary bounded slices on `gpt-6.1-sol`
high. Use `gpt-6-astra` high only for the exact slice carrying the Exceptional
evidence. Do not promote mechanical writing, deterministic migrations,
generated bindings, or straightforward UI work merely because another slice is
Exceptional. Use Astra xhigh only after Astra high makes a conceptual error or
when preflight cites several inseparable Exceptional factors; never select
Astra max automatically.

Every preflight result must name one exact implementation model/effort and one
exact postflight floor, never a range. Use `gpt-6-luna` medium for bounded
exploration and factual lookup: locating files, tracing an established flow,
or extracting facts from documentation. Use Luna high when several sources
must be correlated within a clear factual question. This applies to bounded
factual subtasks even within a higher-profile task; main or the requesting gate
owns the interpretation. Architecture, security judgments, difficult root-cause
analysis, and other decision-determining questions use the requesting gate's
exact tier or the higher tier justified by that question's own risk.

Independent review means a separate reviewer with fresh context at the table's
postflight tier, on the other vendor under Cross-Vendor Review. It does not
automatically require Astra. Use Astra for an
unresolved review question only when its concrete reasoning difficulty meets
the Exceptional criteria; follow the normal preflight and ceiling rules.

Route diagnosis at `gpt-6.1-sol` high for Fast or Standard work,
`gpt-6.1-sol` high for Deep work, and `gpt-6.1-sol` xhigh when the unresolved
cause itself carries the Critical profile. Use `gpt-6-astra` high only when the
unresolved cause itself meets the Exceptional criteria. Diagnosis runs on the
other vendor under Cross-Vendor Review.
Always apply the selected ceiling to diagnosis and specialists.

