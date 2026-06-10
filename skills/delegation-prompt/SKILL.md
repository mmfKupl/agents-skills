---
name: delegation-prompt
description: Prepare a markdown block with copyable task text for another chat. Use when the user wants delegation help but prefers a ready-to-paste task description instead of launching an agent directly.
---

# Delegation Prompt

Use this skill only on explicit request.

## Goal

Produce a compact markdown block that the user can copy into another chat as a ready task description.

Do not call `spawn_agent` yourself when using this skill.

## Defaults

Default to a self-contained task description with no tool-specific execution settings.

Do not include model, reasoning, context inheritance, agent type, waiting mode, or parallel-work instructions in the generated text unless the user explicitly asks to include them.

## Workflow

1. Confirm the user explicitly wants a copyable delegation prompt. If not, do not use this skill.
2. Extract or infer the delegated task and any constraints that the recipient actually needs to execute it.
3. Build a concise self-contained task prompt for the recipient, including any required approval gates for code and test changes.
4. Return only a short intro plus one markdown code block that the user can paste into chat.
5. Do not launch any agent.

## Context Handling

Generate a self-contained prompt by default.

If the user says `minimal`, include only the smallest required facts.
If the user says `current` or `same context`, convert that into a short factual summary instead of mentioning thread inheritance mechanics.

## Override Rules

Honor explicit user requests about what should appear in the generated text.

By default, omit execution metadata that the user can choose manually in the destination chat.

## Code Change Gates

When the delegated task may result in code or test edits, include these rules in the generated prompt:

- Before making any code changes, write in Russian a brief summary of what needs to be changed and wait for explicit user confirmation.
- Do not change tests before the code changes are approved.
- Only after the code changes are approved may the subagent update or add tests.

## Prompt Construction

Write the generated prompt in imperative form and keep it bounded.

Include:

- the exact task
- the expected output
- relevant file paths, issue IDs, URLs, or artifacts
- whether the recipient should edit files or only investigate
- any approval gates that must be followed before editing code or tests
- ownership boundaries if multiple subagents are involved

Do not assume the recipient can see the prior thread.

Do not leak full thread context by default.

## Output Format

Return a short lead-in and one fenced markdown block that the user can paste as-is into another chat.

The generated text should contain only the delegated task, expected output, necessary context, and approval gates in natural language. Do not include execution metadata unless the user explicitly asks for it. Do not include meta-instructions such as asking the recipient to use `$spawn-subagent`.

## Example

```md
Inspect failing auth tests in `front/projects/chat`.

Expected output: identify the root cause and propose the minimal fix.

Before making any code changes, write in Russian a brief summary of what needs to be changed and wait for explicit user confirmation.
Do not change tests before the code changes are approved.
Only after the code changes are approved may you update or add tests.
```
