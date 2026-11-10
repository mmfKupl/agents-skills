#!/bin/sh
# Claude Code UserPromptSubmit hook: remind the chat to keep its title current.
# Claude Code applies a skill only when the model thinks the task needs it, so the
# chat-title skill was skipped in many chats. The printed line is added to the context.
# agent-runner workers set AGENT_RUNNER_JOB and never rename chats.
[ -n "${AGENT_RUNNER_JOB:-}" ] && exit 0
cat >/dev/null
echo "Apply the chat-title skill: before you reply, make sure this chat's title matches its current status and workflow, and rename it if it does not."
exit 0
