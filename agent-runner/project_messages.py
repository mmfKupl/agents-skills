"""The texts that a project chat shows the developer as they are.

The scripts fill these and print them, so that a chat does not compose the same message
anew each time. The texts below are the English ones. A file `messages.yaml` replaces any
of them: the ready one next to the project-master skill, and over it one that the
developer saved in the projects folder of the machine.
"""

from __future__ import annotations

import os
import string
from pathlib import Path
from typing import Any

import agent_projects as projects
from agent_projects import ProjectsError

MESSAGES_VARIABLE = "AGENT_PROJECTS_MESSAGES"

DEFAULTS: dict[str, Any] = {
    # How a step is called in a message: by the skill it runs, or by the kind of its report.
    "steps": {},
    # The section of a report that says how the step ended; the first one found is shown.
    "outcome_sections": ["Verdict"],

    # One ticket in one line. `{ticket}` is the number, as a link when the address is known.
    "ticket": '{ticket} "{title}": {where}',
    "ticket_untitled": "{ticket}: {where}",
    # The same line for a notification on the phone, which shows no markdown.
    "notify_ticket": "{ticket}: {where}",
    "step_unknown": "a run",
    # A step with the few words that say what this run of it does.
    "step_about": "{step} ({about})",
    "where_held": "{step} waits for your word to start",
    "where_waiting": "{step} is in the queue",
    "where_starting": "{step} is starting",
    "where_checking": "a comment is being sorted",
    "where_sorting": "a check decides what to start",
    "where_started": "{step} is going",
    "where_failed": "{step} failed",
    "where_ready": "{step} report is ready",
    # The same in a list of tickets, where the report can be opened from the line.
    "where_ready_link": "{step} [report]({link}) is ready",
    "where_no_report": "{step} ended without a report",
    "where_chat": "a chat works on it: {chats}",
    "where_nothing": "nothing started here",
    "where_open": "{where}, its chat is open: {chat}",

    # The state of a project: `agent-projects board <project>`.
    "board_project": "Project {project}: {covers}.",
    "covers_linear": "the Linear project {name}",
    "covers_tickets": "the tickets {tickets}",
    "covers_assignee": "every ticket assigned to you",
    "covers_none": "no tickets named yet",
    "covers_and": " and ",
    "board_triggers": "Triggers:",
    # Only the triggers that are on are listed.
    "trigger_on": "- {trigger}: {about}",
    # A list of tickets: what stands over it, such as the head of a table, and one
    # ticket in it. `{line}` is the ticket's whole line; a table takes the parts.
    "list_head": "",
    "item": "- {line}",
    "board_unwatched": "No trigger is on, so nothing is watched.",
    # The tickets of a project that are in work, each once, in one table: those whose last
    # report asks the developer something that has no answer on record, those under a
    # trigger that is on, and any other with a run that is not over.
    "work": "Tickets in work:",
    "work_list_head": "| Ticket | Title | Where it stands | Trigger |\n|---|---|---|---|",
    "work_item": "| {ticket} | {title} | {where} | {trigger} |",
    "work_trigger": "`{trigger}`",
    "work_none": "No tickets in work.",
    "where_asks": "waits for your answer: {step}, {count} questions in the [report]({link})",
    "board_read": "The tracker was read at {time}; watching is {watching}.",
    "board_never": "The tracker has not been read yet; watching is {watching}.",
    "watching_running": "running",
    "watching_stopped": "not running",
    "watching_paused": "paused since {time}",

    # One ticket in full: `agent-projects board <project> <ticket>`, and the news of a report.
    # First line: the ticket, what happened, and whether the developer is needed.
    "card_head": "{ticket} · {where}",
    "card_head_needs": "{ticket} · {where} · waits for your answers: {count}",
    # Second line, when the ticket has a pull request; without one it is the title alone.
    "card_title_pr": "{title} · [PR #{number}]({url})",
    # What joins the parts of the last line: the report, its suggestions, how to open the chat.
    "card_join": " · ",
    "card_outcome": "{text}",
    "card_needs": "Needs from you:",
    "card_no_needs": "Nothing is needed from you.",
    "card_report": "Report: [{name}]({link})",
    "card_suggestions": "suggestions: {count}",
    # The screenshots and videos that the report names, each as a link.
    "card_files": "Files of the report: {files}",
    "card_failed": "Reason: {note}",
    "card_again": 'Say "start {ticket} again" to run it once more.',
    "card_last": "Its last message: [{name}]({link})",
    "card_earlier": "Earlier report: [{name}]({link})",
    "card_open": 'say "open {ticket}" to talk to its agent',
    "card_none": "{ticket} has no record on this machine.",

    # News of a project: `agent-projects news <project>`.
    "news_none": "Nothing new.",
    # A line that stands before, between, and after the pieces of news; none when empty.
    "news_rule": "",
    "news_started": '{line}\n{title}\nStarted by the trigger "{trigger}".',
    "news_sorted": '{line}\n{title}\nThe check of the trigger "{trigger}" chose this.',
    # Stands where a ticket's line says where the ticket is.
    "where_nothing_to_start": 'the check of the trigger "{trigger}" found nothing to start ({outcome})',
    "burst": "{count} new events are in the queue, and at most {limit} runs go at once. Say which to drop, if any.",
    # Tickets that came under a trigger or left it: a head with the trigger and how many
    # of each, then a table with only those tickets. `{counts}` is the count texts below,
    # joined by `changed_join`; each has a text of its own for one ticket.
    "changed_head": "Trigger `{trigger}` · {counts}",
    "changed_join": ", ",
    "changed_new_one": "1 new",
    "changed_new": "{count} new",
    "changed_closed_one": "1 closed",
    "changed_closed": "{count} closed",
    "changed_moved_one": "1 left",
    "changed_moved": "{count} left",
    "changed_list_head": "| Ticket | Title | What happened | Where it stands |\n|---|---|---|---|",
    "changed_item": "| {ticket} | {title} | {what} | {where} |",
    "changed_what_new": "new",
    "changed_what_closed": "closed ({status})",
    "changed_what_moved": "now {status}, assigned to {assignee}",
    # The daily summary starts with what it is and whether the developer is needed.
    "summary_head": "{project} · daily summary · wait for your answer: {asks}",
    "summary_finished": "- finished: {ticket} ({step})",
    "summary_failed": "- failed: {ticket} ({step}): {note}",
    "summary_held": "- wait for your word: {tickets}",
    "summary_going": "- running now: {running}; in the queue: {queued}",
    "summary_skipped": "- skipped or sorted as noise: {count}",
    "summary_cost": "- cost of the runs that ended: ${cost}",

    # The line a command answers with under `say`.
    "asked": "{line}, on {model}, {effort}. The outcome will come here.",
    "asked_sorting": "{line}. What it starts will be said here.",
    "trigger_now_on": 'The trigger "{trigger}" is on.',
    "trigger_now_off": 'The trigger "{trigger}" is off.',
    "held_head": "These tickets match already and did not start by themselves:",
    "held_ask": "Which of them to run?",
    "paused": "Watching is paused. Runs that are going and will finish: {running}.",
    "resumed": "Watching is on again.",
    "not_paused": "Watching was not paused.",
    "opened": 'The chat is in the sidebar: "{chat}". Its first answer costs more than a usual one, '
              "because it reads the whole conversation again.",
    "opened_already": 'The chat is open already: "{chat}".',
    "queued": "Queued: {tickets}.",
    "dismissed": "Dropped: {tickets}.",

    # The one line of a notification to the developer's phone. For a ticket it is the
    # line `notify_ticket`; `{line}` here is that line.
    "notify_needs": "{line}, your answer is needed",
    "notify_changed": "Trigger {trigger}: {counts}",
    "notify_summary": "The daily summary for {project} is in the chat",
}

# Slots that a text may use although the English one does not.
MORE_SLOTS = {"item": {"ticket", "title", "where"}}

_cache: dict[str, Any] = {}


def files() -> list[Path]:
    """The files that replace texts, the weakest first."""
    configured = os.environ.get(MESSAGES_VARIABLE)
    if configured is not None:
        return [Path(item).expanduser() for item in configured.split(os.pathsep) if item]
    codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    # Claude Code's skills are links into the repository, so they are never older than Codex's copy.
    return [*(base / "skills" / "project-master" / "messages.yaml" for base in (codex, claude)),
            projects.home() / "messages.yaml"]


def _slots(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def load() -> tuple[dict[str, Any], list[str]]:
    """The texts in use, and what was wrong with the files. A text that names a slot the
    script does not fill is left out, so that a typo never breaks a message."""
    texts: dict[str, Any] = {**DEFAULTS, "steps": {}, "outcome_sections": list(DEFAULTS["outcome_sections"])}
    problems = []
    for path in files():
        if not path.is_file():
            continue
        try:
            document = projects._load_mapping(path)
        except ProjectsError as error:
            problems.append(str(error))
            continue
        for key, value in document.items():
            default = DEFAULTS.get(key)
            if key == "steps" and isinstance(value, dict):
                texts["steps"].update({str(name): str(words) for name, words in value.items()})
            elif key == "outcome_sections" and isinstance(value, list) and all(isinstance(item, str) for item in value):
                texts[key] = value
            elif not isinstance(default, str) or not isinstance(value, str):
                problems.append(f"{path}: `{key}` is not a text that the scripts use")
            else:
                allowed = _slots(default) | MORE_SLOTS.get(key, set())
                try:
                    extra = sorted(_slots(value) - allowed)
                except ValueError:
                    extra = ["a brace that opens or closes nothing"]
                if extra:
                    problems.append(f"{path}: `{key}` has {extra[0]}, which the scripts do not fill; "
                                    f"it may use {', '.join(sorted(allowed)) or 'no slots'}")
                else:
                    texts[key] = value
    return texts, problems


def _loaded() -> tuple[dict[str, Any], list[str]]:
    key = [(str(path), path.stat().st_mtime_ns if path.is_file() else None) for path in files()]
    if _cache.get("key") != key:
        _cache.update(key=key, value=load())
    return _cache["value"]


def texts() -> dict[str, Any]:
    return _loaded()[0]


def problems() -> list[str]:
    return _loaded()[1]


def say(key: str, **slots: Any) -> str:
    return texts()[key].format(**slots)
