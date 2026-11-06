# Model ceiling

Read this when the invocation or the user sets a ceiling, in `M`, `E`, or plain words.

Resolve one immutable model policy at the start of the run, before preflight:

- `adaptive` is the default and applies no ceiling to the routing matrix;
- `explicit_ceiling`, alias `E`, uses the model named by the user, for example
  `E Sol`, `E: Luna`, or "не выше модели Sol";
- `main_ceiling`, alias `M`, uses the model selected for the main chat, for
  example `M` or "не используй модели сильнее модели этого чата".

Interpret an unambiguous cost-saving instruction such as "не используй сильные
модели" in context and resolve it to a concrete `explicit_ceiling`; do not
hard-code that phrase to Sol and do not ask the user to translate it into a
mode. Report the resolved mode and maximum model before the first delegated
job.

The supported ceiling order is strictly `gpt-6-luna` < `gpt-6.1-terra` <
`gpt-6-sol` < `gpt-6.1-sol` < `gpt-6-astra`. Each Claude model shares the rank
of its GPT peer under Cross-Vendor Review, so `E Opus` is as valid as `E Sol`.
A capped job keeps its vendor and takes that vendor's strongest model at or
below the ceiling's rank. `Sol` resolves to `gpt-6.1-sol` for new runs; use the
full `gpt-6-sol` ID to request a previous-generation Sol ceiling. Existing
pinned Sol ceilings retain their recorded model. `Terra` resolves to
`gpt-6.1-terra`; explicit GPT-5.6 model IDs, including `gpt-5.6-terra`, are not
accepted for new runs. Accept `Luna`, `Astra`, `Haiku`, `Sonnet`, `Opus`, and
`Fable` as short names. A ceiling
limits the model only; keep the reasoning effort chosen
by the normal profile. Determine the requested model exactly as in `adaptive`,
then select the lower of that model and the ceiling. Never select a model above
the ceiling.

The ceiling is an explicit user constraint, not a reason to request an upgrade:

- do not ask the user to raise, remove, or bypass it;
- do not return `upgrade required` solely because the adaptive route is above
  it;
- keep every retry, specialist, diagnosis, implementation slice, preflight, and
  postflight at or below it;
- record the adaptive requested model, selected model, and limiting mode when
  they differ;
- if the bounded workflow cannot succeed within the ceiling, report that
  terminal outcome without proposing a model-policy change.

In runner mode, call `agent-run-manifest init --workspace <absolute-worktree>`
as described in `references/agent-runner.md`. It reads the actual user invocation
from all matching rollouts for the current thread, resolves explicit `M`/`E`
itself, and prints the new manifest path. For `M`, the ceiling is the model of
the invocation turn, not a later model switch. Do not delete or move session
files after compaction. Only use `--mode` / `--maximum-model` to express your
interpretation of a natural-language constraint; they cannot override explicit
invocation parameters. Read the generated policy before reporting it.

Prepare each task with its adaptive requested model. `agent-run-manifest new-job`
checks the policy against its pinned source before applying the ceiling and
creating immutable `task.yaml`. Do not change the source or policy to bypass an
error. Recover a missing source/runtime record; never fall back to `adaptive`
when a constrained invocation cannot be resolved.

In direct-subagent mode, apply the same comparison before every `spawn_agent`
call and every manifest-free cross-vendor task, and pass only the selected
model. Include the requested and selected model
in the role packet when the ceiling changed it. Direct subagents have no
manifest enforcement, so this check is mandatory at every spawn.
