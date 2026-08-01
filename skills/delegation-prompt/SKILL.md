---
name: delegation-prompt
description: Prepare a compact copyable task prompt for another chat that names the requested workflow skills, such as `$develop-task` followed by `$review-task`, and summarizes only the task requirements and essential context. Use when the user wants ready-to-paste delegation text instead of launching an agent.
---

# Delegation Prompt

## Goal

Produce one compact prompt that the user can paste into another chat. Carry the
task intent and necessary context; let the named workflow skills own execution,
validation, review, and lifecycle policy.

Do not launch an agent.

## Workflow

1. Identify the task, ticket, or requested outcome and any workflows the user
   wants the recipient to use.
2. For repository implementation work, default to `$develop-task` followed by
   `$review-task`. Use different workflows when the user requests them.
3. Extract the concrete requirements, acceptance criteria, important factual
   context, and explicit non-goals from the conversation. Do not invent missing
   requirements.
4. Compress that information into a short natural-language task brief in the
   user's language.
5. Return one fenced markdown block that can be pasted as-is.

## Prompt Construction

Start by naming the workflows and task, then list what needs to change. For
example:

```md
Используй `$develop-task` для реализации, затем `$review-task` для итоговой проверки задачи UIB-2652.

Нужно:
- <требование или изменение>
- <критерий готовности или важное ограничение>
```

Include only information that helps the recipient understand the task:

- task or ticket identifier and title, when known;
- requested behavior and concrete changes;
- acceptance criteria and task-specific constraints stated by the user;
- essential links, artifacts, or factual context that cannot be recovered from
  the task itself.

Assume the destination chat is already opened in the intended repository. Do
not add a repository, worktree, or current-directory path unless the user asks
for it or the path is itself part of the task.

Omit generic execution mechanics already owned by the named workflows,
including:

- approval gates or instructions to wait for confirmation before editing;
- model, reasoning, agent, delegation, or context-inheritance settings;
- generic test commands, validation checklists, or report templates;
- commit, push, PR, or issue-tracker restrictions;
- boilerplate such as `Доработай <ticket> в репозитории <path>`.

Preserve a task-specific validation requirement, lifecycle constraint, or file
path only when the user explicitly makes it part of the task.

## Output Rules

Keep the generated prompt concise and self-contained. Prefer a workflow sentence
and a short `Нужно:` list over a detailed execution contract. Return no
surrounding explanation unless the user asks for it, and do not explain the
skill itself inside the generated prompt.

Honor explicit user requests about wording, included context, workflows, and
level of detail over these defaults.
