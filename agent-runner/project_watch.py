"""Watch the tracker for the triggers that projects turned on, and start their runs.

No model works here. The script reads Linear, matches what it finds against the trigger
files, and starts a full chat through `agent-run-manifest chat` for each match. When
the chat ends, the script passes one line on to the project chat.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import agent_projects as projects
import run_chat
import run_manifest as manifest
from agent_projects import ProjectsError

LINEAR_URL = "https://api.linear.app/graphql"
KEY_VARIABLE = "AGENT_PROJECTS_LINEAR_KEY_FILE"
TRIGGERS_VARIABLE = "AGENT_PROJECTS_TRIGGERS"
SERVICE = "agent-projects-watch.service"
INTERVAL_SECONDS = 60.0
# `develop-please` moves a ticket under the developer's account as soon as an agent takes
# it. A status change is acted on only after this long, so that the chat that took the
# ticket has written its record.
SETTLE_SECONDS = 120
# What `watch list` shows without --all: everything that is not over.
OPEN_STATES = ("held", "waiting", "started", "failed")
WHO = ("current_user", "not_current_user")
ENTRY_FIELDS = {"source", "event", "to", "from", "assignee", "actor", "skip", "then"}
RUN_FIELDS = {"command", "prompt", "model", "effort"}
ISSUES_QUERY = """
query($filter: IssueFilter, $after: String) {
  issues(filter: $filter, first: 25, after: $after) {
    nodes {
      identifier title url
      state { name }
      assignee { id name }
      history(first: 25) {
        nodes { id createdAt actor { id name } botActor { name } fromState { name } toState { name } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# Runs this process started, kept so that it can tell when each one ends.
_children: dict[int, subprocess.Popen[bytes]] = {}


def _stamp(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# Triggers


def trigger_folders() -> list[Path]:
    configured = os.environ.get(TRIGGERS_VARIABLE)
    if configured:
        return [Path(item).expanduser() for item in configured.split(os.pathsep) if item]
    codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    # A trigger saved on this machine wins over a ready one with the same name.
    return [projects.home() / "triggers",
            *(base / "skills" / "project-master" / "triggers" for base in (codex, claude))]


def _trigger(path: Path) -> dict[str, Any]:
    """Read one trigger file. Anything the script does not understand is an error, so
    that a misspelled condition never widens what a trigger starts."""
    document = projects._load_mapping(path)

    def bad(text: str) -> ProjectsError:
        return ProjectsError(f"{path}: {text}")

    unknown = sorted(set(document) - {"name", "on_any", "run"})
    if unknown:
        raise bad(f"unknown field `{unknown[0]}`")
    name, entries, runs = document.get("name"), document.get("on_any"), document.get("run")
    if not isinstance(name, str) or not name.strip():
        raise bad("`name` must be text")
    if not isinstance(runs, dict) or not runs:
        raise bad("`run` must hold at least one entry")
    known_models = {*manifest.MODEL_ORDER, *manifest.CLAUDE_MODEL_PEERS}
    for key, run in runs.items():
        if run == "skip":
            continue
        if not isinstance(run, dict) or set(run) - RUN_FIELDS or ("command" in run) == ("prompt" in run):
            raise bad(f"run `{key}` must be `skip`, or hold `command` or `prompt`, with `model` and `effort`")
        if not isinstance(run.get("command", run.get("prompt")), str):
            raise bad(f"run `{key}`: the command or prompt must be text")
        if manifest._model_id(str(run.get("model"))) not in known_models:
            raise bad(f"run `{key}`: unknown model {run.get('model')!r}")
        if run.get("effort") not in run_chat.EFFORTS:
            raise bad(f"run `{key}`: `effort` must be one of {', '.join(run_chat.EFFORTS)}")
    if not isinstance(entries, list) or not entries:
        raise bad("`on_any` must list at least one event")
    for entry in entries:
        if not isinstance(entry, dict):
            raise bad("each `on_any` entry must be a mapping")
        unknown = sorted(set(entry) - ENTRY_FIELDS)
        if unknown:
            raise bad(f"unknown field `{unknown[0]}` in an `on_any` entry")
        if entry.get("source") != "linear" or entry.get("event") != "status_changed":
            raise bad("this version reads only `source: linear` with `event: status_changed`")
        if not isinstance(entry.get("to"), str) or not isinstance(entry.get("from", ""), str):
            raise bad("a status_changed entry needs `to`, a status name; `from` is optional")
        for field in ("assignee", "actor"):
            if entry.get(field, WHO[0]) not in WHO:
                raise bad(f"`{field}` must be {' or '.join(WHO)}")
        if entry.get("skip", "ticket_taken_in_current_env") != "ticket_taken_in_current_env":
            raise bad("`skip` must be ticket_taken_in_current_env")
        if entry.get("then") not in runs:
            raise bad("`then` must name an entry of `run`")
    return {"name": name.strip(), "on_any": entries, "run": runs, "file": str(path)}


def load_triggers() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return every usable trigger by name, and what is wrong with the rest."""
    found: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for folder in trigger_folders():
        for path in sorted(folder.glob("*.yaml")):
            try:
                trigger = _trigger(path)
            except ProjectsError as error:
                problems.append(str(error))
                continue
            found.setdefault(trigger["name"], trigger)
    return found, problems


def trigger_list() -> dict[str, Any]:
    triggers, problems = load_triggers()
    listing = [
        {"name": trigger["name"], "file": trigger["file"],
         "when": [" ".join(f"{key}={value}" for key, value in entry.items()) for entry in trigger["on_any"]],
         "runs": {key: run if run == "skip" else f"{run.get('command') or 'a prompt'} ({run['model']}, {run['effort']})"
                  for key, run in trigger["run"].items()}}
        for trigger in triggers.values()
    ]
    return {"triggers": listing, **({"problems": problems} if problems else {})}


# Linear


def linear_key_file() -> Path:
    configured = os.environ.get(KEY_VARIABLE)
    return Path(configured).expanduser() if configured else Path.home() / ".config" / "agent-projects" / "linear-api-key"


def linear(query: str, variables: dict[str, Any] | None = None, timeout: float = 30) -> dict[str, Any]:
    """Send one read query. The key goes only into the request header, never into a message."""
    path = linear_key_file()
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ProjectsError(f"the Linear key is missing: {path}") from error
    request = urllib.request.Request(
        LINEAR_URL, data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        reason = "the key is not accepted" if error.code in (401, 403) else error.read(300).decode("utf-8", "replace")
        raise ProjectsError(f"Linear answered {error.code}: {reason}") from error
    except (OSError, ValueError) as error:
        raise ProjectsError(f"Linear cannot be reached: {error}") from error
    if payload.get("errors"):
        raise ProjectsError(f"Linear refused the query: {payload['errors'][0].get('message')}")
    return payload["data"]


def _current_user(state: dict[str, Any]) -> str:
    """The account the key belongs to, asked once per key file."""
    path = linear_key_file()
    try:
        saved = path.stat().st_mtime
    except OSError as error:
        raise ProjectsError(f"the Linear key is missing: {path}") from error
    user = state.get("current_user") or {}
    if user.get("key_saved") != saved:
        viewer = linear("query { viewer { id name } }")["viewer"]
        user = state["current_user"] = {"id": viewer["id"], "name": viewer["name"], "key_saved": saved}
    return user["id"]


def _issues(scope: dict[str, Any], statuses: list[str]) -> list[dict[str, Any]]:
    """Every ticket the project covers that is now in one of the statuses."""
    filters: list[dict[str, Any]] = []
    if scope.get("linear_project"):
        filters.append({"project": {"name": {"eq": str(scope["linear_project"])}}})
    numbers: dict[str, list[int]] = {}
    for ticket in scope.get("tickets") or []:
        parts = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)-([0-9]+)", str(ticket))
        if parts:
            numbers.setdefault(parts[1].upper(), []).append(int(parts[2]))
    filters += [{"team": {"key": {"eq": team}}, "number": {"in": chosen}} for team, chosen in sorted(numbers.items())]
    if not filters:
        raise ProjectsError("its scope names no Linear project and no tickets")
    found: dict[str, dict[str, Any]] = {}
    for scope_filter in filters:
        after = None
        for _ in range(20):
            variables = {"filter": {**scope_filter, "state": {"name": {"in": statuses}}}, "after": after}
            page = linear(ISSUES_QUERY, variables)["issues"]
            found.update({issue["identifier"]: issue for issue in page["nodes"]})
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
    return [found[key] for key in sorted(found)]


def _is(rule: str | None, person: str | None, me: str) -> bool:
    return rule is None or (person == me) == (rule == "current_user")


def _matches(entry: dict[str, Any], issue: dict[str, Any], move: dict[str, Any], me: str) -> bool:
    status = issue["state"]["name"]
    return (
        status == entry["to"] == move["toState"]["name"]
        and ("from" not in entry or (move.get("fromState") or {}).get("name") == entry["from"])
        and _is(entry.get("assignee"), (issue.get("assignee") or {}).get("id"), me)
        and _is(entry.get("actor"), (move.get("actor") or {}).get("id"), me)
    )


# The watcher's own record


def paused() -> str | None:
    path = projects.home() / "paused"
    return (path.read_text(encoding="utf-8").strip() or "an unknown time") if path.is_file() else None


def _read_state(root: Path) -> dict[str, Any]:
    path = root / "watch.yaml"
    state = projects._load_mapping(path) if path.is_file() else {}
    for key in ("baseline", "events", "problems"):
        state.setdefault(key, [])
    return state


@contextmanager
def _state() -> Iterator[dict[str, Any]]:
    """Load the record under a lock and save it on the way out; an error saves nothing."""
    root = projects._require_home()
    path = root / "watch.yaml"
    with projects._locked(path):
        state = _read_state(root)
        yield state
        projects._atomic_write(path, projects._dump(state))


def _public(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key not in ("key", "pid")}


def poll(now: datetime | None = None) -> dict[str, Any]:
    """Read the tracker once and record what matched. Starts nothing.

    A status trigger is judged by where a ticket is now: it is in the trigger's status,
    and the move that put it there fits the entry. One move is recorded once, so a ticket
    that leaves the status and comes back counts again.
    """
    root = projects._require_home()
    since = paused()
    if since:
        return {"paused": since}
    now = now or datetime.now(timezone.utc)
    triggers, problems = load_triggers()
    new: list[dict[str, Any]] = []
    with _state() as state:
        known = {event["key"] for event in state["events"]}
        for name in projects._project_names(root):
            _, project = projects._load_project(root, name)
            wanted = project.get("triggers") or []
            if not wanted:
                continue
            active = [triggers[item] for item in wanted if item in triggers]
            problems += [f"project {name}: no trigger named {item!r}" for item in wanted if item not in triggers]
            if not active:
                continue
            try:
                if project.get("tracker") != "linear":
                    raise ProjectsError("triggers need the linear tracker")
                me = _current_user(state)
                statuses = sorted({entry["to"] for trigger in active for entry in trigger["on_any"]})
                issues = _issues(project.get("scope") or {}, statuses)
            except ProjectsError as error:
                problems.append(f"project {name}: {error}")
                continue
            for trigger in active:
                pair = f"{name}|{trigger['name']}"
                # What already matched when the trigger was turned on, or what came in
                # during a pause, is the developer's call, not an automatic start.
                first = pair not in state["baseline"]
                for issue in issues:
                    moves = [node for node in issue["history"]["nodes"] if node.get("toState")]
                    if not moves:
                        continue
                    move = max(moves, key=lambda node: node["createdAt"])
                    hit = next(((index, entry) for index, entry in enumerate(trigger["on_any"])
                                if _matches(entry, issue, move, me)), None)
                    if hit is None:
                        continue
                    index, entry = hit
                    key = f"{trigger['name']}|{index}|{move['id']}"
                    if key in known:
                        continue
                    moved = _time(move["createdAt"])
                    if not first and (now - moved).total_seconds() < SETTLE_SECONDS:
                        continue
                    ticket = projects._ticket_id(issue["identifier"])
                    path = projects._ticket_path(root, ticket)
                    holders = [projects._who(item) for item in projects._load_ticket(path, ticket)[0]["taken"]]
                    if trigger["run"][entry["then"]] == "skip":
                        verdict, note = "skipped", "the trigger says skip"
                    elif entry.get("skip") and holders:
                        verdict, note = "skipped", f"a chat here already works on it: {', '.join(holders)}"
                    elif first:
                        verdict, note = "held", "matched before watching began or while it was paused"
                    else:
                        verdict, note = "waiting", None
                    actor = (move.get("actor") or move.get("botActor") or {}).get("name") or "an integration"
                    state["next_id"] = state.get("next_id", 0) + 1
                    event = {
                        "id": state["next_id"], "key": key, "project": name, "trigger": trigger["name"],
                        "run": entry["then"], "ticket": ticket, "title": issue.get("title"), "url": issue.get("url"),
                        "what": f"moved from {(move.get('fromState') or {}).get('name') or 'no status'} "
                                f"to {entry['to']} by {actor} at {_stamp(moved)}",
                        "found": _stamp(now), "state": verdict, **({"note": note} if note else {}),
                    }
                    state["events"].append(event)
                    known.add(key)
                    new.append(event)
                if first:
                    state["baseline"].append(pair)
        state["polled"], state["problems"] = _stamp(now), problems
        held = [_public(event) for event in state["events"] if event["state"] == "held"]
    return {"polled": _stamp(now), "new": [_public(event) for event in new], "held": held,
            **({"problems": problems} if problems else {})}


# Runs


def _fresh(path: Path) -> Path:
    number, chosen = 1, path
    while chosen.exists():
        number += 1
        chosen = path.with_name(f"{path.name}-{number}")
    return chosen


def _spawn_chat(repository: str, model: str, effort: str, prompt: str, run_dir: Path,
                name: str | None = None, worktree: str | None = None) -> int:
    """Start a full chat that outlives this process, and return its process id."""
    run_dir.mkdir(parents=True)
    prompt_file = run_dir / "trigger-prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    command = [sys.executable, "-m", "run_manifest", "chat", "--workspace", repository, "--model", model,
               "--effort", effort, "--prompt-file", str(prompt_file), "--run-dir", str(run_dir),
               # Nobody is there to approve a tool call.
               "--unrestricted"]
    command += ["--name", name] if name else []
    command += ["--worktree", worktree] if worktree else []
    modules = [str(Path(__file__).resolve().parent), os.environ.get("PYTHONPATH")]
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(item for item in modules if item)}
    with (run_dir / "runner.log").open("ab") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, env=environment)
    _children[process.pid] = process
    return process.pid


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    child = _children.get(pid)
    if child is not None:
        if child.poll() is None:
            return True
        del _children[pid]
        return False
    # A run that an earlier watcher process started is not this process's child.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _start(event: dict[str, Any], root: Path, triggers: dict[str, dict[str, Any]]) -> None:
    try:
        _, project = projects._load_project(root, event["project"])
        run = (triggers.get(event["trigger"]) or {"run": {}})["run"].get(event["run"])
        if not isinstance(run, dict):
            raise ProjectsError(f"the trigger {event['trigger']!r} no longer has the run {event['run']!r}")
        vendor, _ = run_chat.chat_route(run["model"], "auto")
        sigil = "/" if vendor == "claude" else "$"
        text = (run.get("command") or run["prompt"]).strip().replace("{ticket}", event["ticket"])
        if "command" in run:
            text = sigil + text.lstrip("/$")
        prompt = (
            f"{sigil}project-scope {event['project']} {text}\n\n"
            f"Started by the trigger \"{event['trigger']}\": {event['ticket']} was {event['what']}.\n"
            "The developer is not in this chat. Do not wait for an answer: put every question into the report.\n"
        )
        stem = re.sub(r"[^a-z0-9-]+", "-", f"{event['ticket']}-{event['run']}-{event['id']}".lower())
        run_dir = _fresh(projects._project_dir(root, event["project"]) / "runs" / f"{_stamp()[:10]}-{stem}")
        pid = _spawn_chat(project["repository"], run["model"], run["effort"], prompt, run_dir,
                          name=f"{event['run']}: {event['ticket']}", worktree=run_dir.name[11:])
    except (ProjectsError, manifest.ManifestError, OSError, KeyError) as error:
        event.update(state="failed", note=f"could not start: {error}")
        return
    event.update(state="started", started=_stamp(), run_dir=str(run_dir), pid=pid)
    event.pop("note", None)


def _finish(event: dict[str, Any], root: Path) -> str | None:
    """Close a started event once its run has ended, and return the line for the project
    chat. The script sends it, because a run on a cheap model may skip that step."""
    if _alive(event.get("pid")):
        return None
    record_path = Path(event["run_dir"]) / "chat.yaml"
    try:
        record = projects._load_mapping(record_path) if record_path.is_file() else {}
    except ProjectsError:
        record = {}
    last = (record.get("turns") or [{}])[-1]
    event["finished"] = _stamp()
    event.pop("pid", None)
    label = f"{event['ticket']}: the {event['run']} run that the trigger \"{event['trigger']}\" started"
    if record.get("status") == "completed":
        event["state"] = "finished"
        path = projects._ticket_path(root, event["ticket"])
        reports = [report for report in projects._load_ticket(path, event["ticket"])[0]["reports"]
                   if str(report.get("at", "")) >= event["started"]]
        if reports:
            return (f"{event['ticket']}: {reports[-1].get('kind')} report ready, started by the trigger "
                    f"\"{event['trigger']}\". {reports[-1].get('path')}")
        event["note"] = "the run ended without filing a report"
        return f"{label} ended without filing a report. Its last message: {last.get('result')}"
    event["state"] = "failed"
    known = record.get("status") in ("failed", "timed_out")
    event["note"] = str(last.get("error") or "no reason recorded") if known else "the run stopped without a result"
    projects.ticket_note(event["ticket"], f"{event['run']} run from the trigger \"{event['trigger']}\" failed: {event['note']}")
    return f"{label} failed: {event['note']}. `agent-projects watch start {event['id']}` starts it again."


def _tell(root: Path, project_name: str, text: str) -> None:
    """Pass a line to the project chat. Only a chat can message a chat, so a small one does it."""
    _, project = projects._load_project(root, project_name)
    chat = project.get("chat") or {}
    if chat.get("host") != "claude" or not chat.get("title"):
        return
    prompt = (
        "Send one message to another chat on this machine, then stop.\n\n"
        "1. The tool is SendMessage. If it is not loaded, load it with ToolSearch: `select:SendMessage,ListAgents`.\n"
        f"2. Send the text between the two lines of dashes, unchanged, to the chat named \"{chat['title']}\".\n"
        "3. If the tool refuses or finds no such chat, run ListAgents once and answer with what it showed. "
        "Try nothing else.\n\n"
        f"---\n{text}\n---\n"
    )
    run_dir = _fresh(projects._project_dir(root, project_name) / "runs" / f"{_stamp()[:10]}-message")
    _spawn_chat(project["repository"], "haiku", "low", prompt, run_dir)


def cycle() -> list[str]:
    """One round of the loop: read the tracker, start what waits, close what ended."""
    root = projects._require_home()
    found = poll()
    lines = [f"{event['ticket']}: {event['state']} for {event['trigger']} ({event['what']})"
             for event in found.get("new", [])]
    triggers, _ = load_triggers()
    to_tell: list[tuple[str, str]] = []
    with _state() as state:
        state["loop"] = _stamp()
        for event in state["events"]:
            before = event["state"]
            if before == "waiting" and not found.get("paused"):
                _start(event, root, triggers)
            elif before == "started":
                line = _finish(event, root)
                if line:
                    to_tell.append((event["project"], line))
            if event["state"] != before:
                lines.append(f"{event['ticket']}: {event['run']} run {event['state']}"
                             + (f" ({event['note']})" if event.get("note") else ""))
        problems = list(state["problems"])
    for project_name, line in to_tell:
        try:
            _tell(root, project_name, line)
        except (ProjectsError, OSError) as error:
            problems.append(f"could not tell the project chat of {project_name}: {error}")
    for pid in list(_children):
        _alive(pid)
    return lines + [f"problem: {problem}" for problem in problems]


def run_loop(interval: float) -> None:
    said: list[str] = []
    while True:
        try:
            lines = cycle()
        except ProjectsError as error:
            lines = [f"problem: {error}"]
        # A problem that stays is said once, not every round.
        fresh = [line for line in lines if not line.startswith("problem: ") or line not in said]
        said = [line for line in lines if line.startswith("problem: ")]
        for line in fresh:
            print(f"{_stamp()} {line}", file=sys.stderr, flush=True)
        time.sleep(interval)


# Commands


def _watching(state: dict[str, Any]) -> str:
    since = paused()
    if since:
        return f"paused since {since}"
    loop = state.get("loop")
    running = bool(loop) and (datetime.now(timezone.utc) - _time(loop)).total_seconds() < 5 * INTERVAL_SECONDS
    return "running" if running else "not running"


def summary() -> dict[str, str]:
    """What `init` says about watching."""
    key = linear_key_file()
    if not key.is_file():
        access = f"no key: {key}"
    else:
        try:
            access = f"works, as {linear('query { viewer { name } }', timeout=10)['viewer']['name']}"
        except ProjectsError as error:
            access = str(error)
    root = projects.home()
    return {"linear": access, "watching": _watching(_read_state(root) if root.is_dir() else {})}


def project_triggers(name: str, on: list[str], off: list[str]) -> dict[str, Any]:
    root = projects._require_home()
    triggers, problems = load_triggers()
    path, _ = projects._load_project(root, name)
    for item in on:
        if item not in triggers:
            raise ProjectsError(f"no trigger named {item!r}; `agent-projects trigger list` shows them")
    with projects._locked(path):
        _, document = projects._load_project(root, name)
        if on and document.get("tracker") != "linear":
            raise ProjectsError("triggers need a project with the linear tracker")
        current = [item for item in document.get("triggers") or [] if item not in off]
        current += [item for item in on if item not in current]
        document["triggers"] = current
        projects._atomic_write(path, projects._dump(document))
    if on or off:
        changed = {f"{name}|{item}" for item in (*on, *off)}
        with _state() as state:
            state["baseline"] = [pair for pair in state["baseline"] if pair not in changed]
    warnings = []
    for other in projects._project_names(root):
        _, theirs = projects._load_project(root, other)
        shared = sorted(set(current) & set(theirs.get("triggers") or []))
        if other != name and shared and theirs.get("scope") == document.get("scope"):
            warnings.append(f"project {other} covers the same tickets with {', '.join(shared)}; "
                            "each ticket goes to one project only")
    return {"project": name, "triggers": current, "available": sorted(triggers),
            **({"warnings": warnings} if warnings else {}), **({"problems": problems} if problems else {})}


def pause() -> dict[str, Any]:
    root = projects._require_home()
    path = root / "paused"
    if not path.is_file():
        projects._atomic_write(path, f"{_stamp()}\n")
    running = [_public(event) for event in _read_state(root)["events"] if event["state"] == "started"]
    return {"paused": paused(), "still_running": running}


def resume() -> dict[str, Any]:
    root = projects._require_home()
    path = root / "paused"
    if not path.is_file():
        return {"resumed": False, "note": "watching was not paused"}
    # Forget the baseline first, so that whatever came in meanwhile is held for the developer.
    with _state() as state:
        state["baseline"] = []
    path.unlink()
    return {"resumed": True, **poll()}


def events(project: str | None, everything: bool) -> dict[str, Any]:
    state = _read_state(projects._require_home())
    chosen = [_public(event) for event in state["events"]
              if (everything or event["state"] in OPEN_STATES) and project in (None, event["project"])]
    return {"events": chosen, "polled": state.get("polled"), "watching": _watching(state),
            **({"problems": state["problems"]} if state["problems"] else {})}


def decide(ids: list[int], target: str) -> dict[str, Any]:
    """Move events to `waiting`, which the watching loop starts, or to `dismissed`."""
    allowed = {"waiting": ("held", "failed", "skipped"), "dismissed": ("held", "failed", "waiting", "skipped")}[target]
    with _state() as state:
        by_id = {event["id"]: event for event in state["events"]}
        for number in ids:
            if number not in by_id:
                raise ProjectsError(f"no event {number}; `agent-projects watch list` shows them")
            if by_id[number]["state"] not in allowed:
                raise ProjectsError(f"event {number} is {by_id[number]['state']}; only {', '.join(allowed)} can change")
        for number in ids:
            by_id[number]["state"] = target
            by_id[number].pop("note", None)
        changed = [_public(by_id[number]) for number in ids]
        watching = _watching(state)
    return {"events": changed, "watching": watching}


def _unit(command: Path) -> str:
    variables = [f"PATH={os.environ.get('PATH', '')}"]
    variables += [f"{name}={os.environ[name]}" for name in (projects.HOME_VARIABLE, KEY_VARIABLE, TRIGGERS_VARIABLE,
                                                             "CODEX_HOME", "CLAUDE_CONFIG_DIR") if os.environ.get(name)]
    return "\n".join([
        "[Unit]",
        "Description=agent-projects: watch the tracker and start trigger runs",
        "",
        "[Service]",
        f"ExecStart={command} watch run",
        *(f'Environment="{variable}"' for variable in variables),
        "Restart=always",
        "RestartSec=30",
        # A restart of the watcher must not stop the runs it started.
        "KillMode=process",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ])


def _systemctl(*arguments: str) -> str:
    done = subprocess.run(["systemctl", "--user", *arguments], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return done.stdout.strip()


def _unit_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user" / SERVICE


def install() -> dict[str, Any]:
    command = Path(sys.executable).parent / "agent-projects"
    if not sys.platform.startswith("linux") or not shutil.which("systemctl") or not command.is_file():
        raise ProjectsError("the service needs systemd and an installed agent-projects; "
                            "elsewhere keep `agent-projects watch run` running yourself")
    path = _unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    projects._atomic_write(path, _unit(command))
    _systemctl("daemon-reload")
    _systemctl("enable", SERVICE)
    _systemctl("restart", SERVICE)
    return {"service": SERVICE, "file": str(path), "state": _systemctl("is-active", SERVICE)}


def uninstall() -> dict[str, Any]:
    path = _unit_path()
    if shutil.which("systemctl"):
        _systemctl("disable", "--now", SERVICE)
    existed = path.is_file()
    if existed:
        path.unlink()
        _systemctl("daemon-reload")
    return {"service": SERVICE, "removed": existed}


def add_commands(commands: Any, project: Any) -> None:
    triggers = project.add_parser("triggers", help="show a project's triggers, or turn some on or off")
    triggers.add_argument("name")
    triggers.add_argument("--on", action="append", default=[], metavar="TRIGGER")
    triggers.add_argument("--off", action="append", default=[], metavar="TRIGGER")
    commands.add_parser("trigger", help="show the triggers this machine has").add_subparsers(
        dest="action", required=True).add_parser("list", help="print every trigger with what it starts")
    commands.add_parser("pause", help="stop reading the tracker and starting runs; running ones finish")
    commands.add_parser("resume", help="watch again, and hold what came in meanwhile for the developer")
    watch = commands.add_parser("watch", help="read the tracker for triggers and start their runs").add_subparsers(
        dest="action", required=True)
    watch.add_parser("poll", help="read the tracker once and record what matched; starts nothing")
    loop = watch.add_parser("run", help="keep watching: poll, start what waits, close what ended")
    loop.add_argument("--interval", type=float, default=INTERVAL_SECONDS, help="seconds between rounds")
    listing = watch.add_parser("list", help="print the events that are not over")
    listing.add_argument("--project")
    listing.add_argument("--all", action="store_true", help="also finished, skipped, and dismissed events")
    watch.add_parser("start", help="let the watching loop start held, failed, or skipped events").add_argument(
        "ids", nargs="+", type=int)
    watch.add_parser("dismiss", help="drop events without running them").add_argument("ids", nargs="+", type=int)
    watch.add_parser("install", help="keep `watch run` running as a systemd user service")
    watch.add_parser("uninstall", help="stop and remove that service")


def run(args: argparse.Namespace) -> dict[str, Any] | str:
    if args.command == "project":
        return project_triggers(args.name, args.on, args.off)
    if args.command == "trigger":
        return trigger_list()
    if args.command == "pause":
        return pause()
    if args.command == "resume":
        return resume()
    if args.action == "poll":
        return poll()
    if args.action == "run":
        run_loop(args.interval)
    if args.action == "list":
        return events(args.project, args.all)
    if args.action in ("start", "dismiss"):
        return decide(args.ids, "waiting" if args.action == "start" else "dismissed")
    return install() if args.action == "install" else uninstall()
