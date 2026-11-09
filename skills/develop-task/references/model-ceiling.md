# Model ceiling

Read this when the invocation or the user sets a ceiling, in `M`, `E`, or plain words.

- `adaptive` is the default: no ceiling.
- `explicit_ceiling` (`E`) uses the model the user named: `E Sol`, `E: Luna`, `E Opus`, or
  "не выше модели Sol". Short names are Luna, Terra, Sol, Astra, Haiku, Sonnet, Opus, and
  Fable; a Claude model shares its GPT peer's rank.
- `main_ceiling` (`M`) uses the model of the main chat at the invocation turn: `M`, or "не
  используй модели сильнее модели этого чата".

Interpret an unambiguous cost-saving instruction such as "не используй сильные модели" in
context as a concrete `explicit_ceiling`; do not hard-code that phrase to Sol or ask the user
to translate it. `init` resolves explicit `M`/`E` itself; pass only your reading of plain
words through its `--mode` and `--maximum-model`. Report the mode and maximum model before
the first job.

The helpers enforce it: `dispatch` and `new-job` check the policy against its pinned source
and cap every job, keeping its vendor and its effort. Do not change the source or policy to
get past an error, and never fall back to `adaptive` when a constrained invocation cannot be
resolved: recover the missing record.

The ceiling is the user's constraint, not a reason to upgrade. Never ask the user to raise,
remove, or bypass it, and do not return `upgrade required` only because the normal route is
above it. If the bounded workflow cannot succeed within it, report that outcome without
proposing a policy change.
