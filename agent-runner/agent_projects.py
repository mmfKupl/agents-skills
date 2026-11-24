#!/usr/bin/env python3
"""Projects, ticket records, and reports shared by every agent chat on one machine."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

HOME_VARIABLE = "AGENT_PROJECTS_HOME"
WORKFLOWS = ("review", "brainstorm", "develop", "draft", "other")
TRACKERS = ("linear", "files")
SKIPPED = "skipped: the agent-projects folder does not exist"
PROJECT_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
TICKET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
REPORT_KIND = re.compile(r"[a-z][a-z0-9-]*")


class ProjectsError(ValueError):
    pass


def home() -> Path:
    configured = os.environ.get(HOME_VARIABLE)
    return Path(configured).expanduser() if configured else Path.home() / "agent-projects"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _chat(chat_id: str | None = None) -> dict[str, str]:
    """The calling chat: Codex and Claude Code each export their own session variable."""
    codex, claude = os.environ.get("CODEX_THREAD_ID"), os.environ.get("CLAUDE_CODE_SESSION_ID")
    host = "codex" if codex else "claude" if claude else "unknown"
    return {"id": chat_id or codex or claude or "unknown", "host": host}


def _project_name(value: str) -> str:
    if not PROJECT_NAME.fullmatch(value):
        raise ProjectsError(f"project name must be lowercase letters, digits, and dashes: {value!r}")
    return value


def _ticket_id(value: str) -> str:
    if not TICKET_ID.fullmatch(value) or ".." in value:
        raise ProjectsError(f"ticket id must be letters, digits, dots, dashes, underscores: {value!r}")
    # Tracker ids such as uib-123 are written in upper case; other ids stay as given.
    return value.upper() if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*-[0-9]+", value) else value


def _require_home() -> Path:
    root = home()
    if not root.is_dir():
        raise ProjectsError(f"{root} does not exist; run `agent-projects init` first")
    return root


def _project_dir(root: Path, name: str) -> Path:
    return root / f"project-{_project_name(name)}"


def _atomic_write(path: Path, text: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    # Several chats write the same ticket and project files at once.
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def _dump(document: Any) -> str:
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000)


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ProjectsError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(document, dict):
        raise ProjectsError(f"{path} must hold a YAML mapping")
    return document


def _load_project(root: Path, name: str) -> tuple[Path, dict[str, Any]]:
    path = _project_dir(root, name) / "project.yaml"
    if not path.is_file():
        raise ProjectsError(f"project {name!r} does not exist; create it with `agent-projects project create`")
    return path, _load_mapping(path)


def _ticket_path(root: Path, ticket: str) -> Path:
    return root / "tickets" / f"{ticket}.md"


def _load_ticket(path: Path, ticket: str) -> tuple[dict[str, Any], str]:
    """A ticket file is YAML front matter the command owns, then a history a person may edit."""
    if not path.is_file():
        return {"ticket": ticket, "projects": [], "taken": [], "reports": [], "links": {}}, f"# {ticket}\n\n## History\n\n"
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ProjectsError(f"{path} must start with YAML front matter between `---` lines")
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise ProjectsError(f"{path} front matter is not valid YAML: {error}") from error
    if not isinstance(meta, dict):
        raise ProjectsError(f"{path} front matter must be a YAML mapping")
    for key, empty in (("projects", []), ("taken", []), ("reports", []), ("links", {})):
        meta.setdefault(key, empty)
    return meta, parts[2].lstrip("\n")


def _save_ticket(path: Path, meta: dict[str, Any], body: str) -> None:
    _atomic_write(path, f"---\n{_dump(meta)}---\n\n{body}")


def _event(body: str, text: str) -> str:
    line = f"- {_now()} {' '.join(text.split())}\n"
    head = body.rstrip()
    if not head:
        return line
    # Events form one list; anything else before them, such as a heading, gets a blank line.
    return f"{head}\n{line}" if head.splitlines()[-1].startswith("- ") else f"{head}\n\n{line}"


def _who(entry: dict[str, Any]) -> str:
    title = entry.get("title")
    return f'"{title}" ({entry["host"]})' if title else f'chat {entry["id"]} ({entry["host"]})'


def init() -> dict[str, Any]:
    root = home()
    created = not root.is_dir()
    for directory in (root, root / "tickets", root / "triggers"):
        directory.mkdir(parents=True, exist_ok=True)
    import project_watch

    return {"home": str(root), "created": created, "projects": _project_names(root), **project_watch.summary()}


def _project_names(root: Path) -> list[str]:
    return sorted(path.parent.name.removeprefix("project-") for path in root.glob("project-*/project.yaml"))


def project_create(name: str, repository: str, tracker: str, scope: list[str], tickets: list[str],
                   section: bool = True) -> dict[str, Any]:
    root = _require_home()
    folder = _project_dir(root, name)
    path = folder / "project.yaml"
    if path.exists():
        raise ProjectsError(f"project {name!r} already exists: {path}")
    scope_map: dict[str, Any] = {}
    for item in scope:
        key, _, value = item.partition("=")
        # A key the watching script does not read would cover nothing and say nothing.
        if not value or key not in ("linear_project", "assignee") or (key == "assignee" and value != "current_user"):
            raise ProjectsError(f"--scope takes linear_project=<name> or assignee=current_user, got {item!r}")
        scope_map[key] = value
    if tickets:
        scope_map["tickets"] = [_ticket_id(ticket) for ticket in tickets]
    (folder / "reports").mkdir(parents=True, exist_ok=True)
    document = {
        "name": name,
        "repository": str(Path(repository).expanduser()),
        "tracker": tracker,
        "scope": scope_map,
        "triggers": [],
        # Whether the project's chats file themselves into one sidebar section.
        "section": section,
        "created": _now(),
    }
    _atomic_write(path, _dump(document))
    return {**document, "folder": str(folder)}


def project_show(name: str) -> dict[str, Any]:
    root = _require_home()
    _, document = _load_project(root, name)
    # A project made before the field existed has the default, which is on.
    return {**document, "section": document.get("section", True), "folder": str(_project_dir(root, name))}


def project_section(name: str, on: bool) -> dict[str, Any]:
    """Turn on or off the filing of the project's chats into one sidebar section."""
    root = _require_home()
    path, _ = _load_project(root, name)
    with _locked(path):
        _, document = _load_project(root, name)
        document["section"] = on
        _atomic_write(path, _dump(document))
    return {"project": name, "section": on}


def project_chat(name: str, title: str | None, chat_id: str | None) -> dict[str, Any]:
    """Remember which chat manages the project, so that runs know where to report."""
    root = _require_home()
    path, _ = _load_project(root, name)
    with _locked(path):
        _, document = _load_project(root, name)
        document["chat"] = {**_chat(chat_id), **({"title": title} if title else {}), "since": _now()}
        _atomic_write(path, _dump(document))
    return {"project": name, "chat": document["chat"]}


def ticket_take(
    ticket: str, workflow: str, project: str | None, title: str | None, cwd: str | None, chat_id: str | None,
) -> dict[str, Any] | str:
    root = home()
    if not root.is_dir():
        return SKIPPED
    ticket = _ticket_id(ticket)
    if project:
        _load_project(root, project)
    path = _ticket_path(root, ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    chat = _chat(chat_id)
    with _locked(path):
        meta, body = _load_ticket(path, ticket)
        mine = next((entry for entry in meta["taken"] if entry.get("id") == chat["id"]), None)
        if mine is None:
            mine = {**chat, "since": _now()}
            meta["taken"].append(mine)
        changed = mine.get("workflow") != workflow
        mine.update({"workflow": workflow, "cwd": cwd or os.getcwd(), **({"title": title} if title else {})})
        # A working copy that Claude Code made for the chat is remembered after the
        # release too, so that it can be removed once the ticket is closed.
        copies = meta.setdefault("copies", [])
        if "/.claude/worktrees/" in f"{mine['cwd']}/" and all(copy.get("cwd") != mine["cwd"] for copy in copies):
            copies.append({"cwd": mine["cwd"], "chat": chat["id"]})
        if project and project not in meta["projects"]:
            meta["projects"].append(project)
        if changed:
            body = _event(body, f"taken for {workflow} by {_who(mine)}")
        _save_ticket(path, meta, body)
    others = [
        {key: entry.get(key) for key in ("title", "host", "workflow", "since", "id")}
        for entry in meta["taken"] if entry.get("id") != chat["id"]
    ]
    return {"ticket": ticket, "file": str(path), "taken_by_this_chat": True, "also_taken_by": others}


def ticket_release(ticket: str, result: str | None, pull_request: str | None, chat_id: str | None) -> dict[str, Any] | str:
    root = home()
    if not root.is_dir():
        return SKIPPED
    ticket = _ticket_id(ticket)
    path = _ticket_path(root, ticket)
    if not path.is_file():
        return {"ticket": ticket, "released": False}
    chat = _chat(chat_id)
    with _locked(path):
        meta, body = _load_ticket(path, ticket)
        mine = [entry for entry in meta["taken"] if entry.get("id") == chat["id"]]
        meta["taken"] = [entry for entry in meta["taken"] if entry.get("id") != chat["id"]]
        if pull_request:
            meta["links"]["pr"] = pull_request
        if mine or result:
            who = _who(mine[0]) if mine else f"chat {chat['id']} ({chat['host']})"
            body = _event(body, f"released by {who}" + (f": {result}" if result else ""))
        _save_ticket(path, meta, body)
    return {"ticket": ticket, "released": bool(mine), "file": str(path)}


def ticket_note(ticket: str, text: str) -> dict[str, Any] | str:
    root = home()
    if not root.is_dir():
        return SKIPPED
    ticket = _ticket_id(ticket)
    if not text.strip():
        raise ProjectsError("the note is empty")
    path = _ticket_path(root, ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(path):
        meta, body = _load_ticket(path, ticket)
        _save_ticket(path, meta, _event(body, text))
    return {"ticket": ticket, "file": str(path)}


def ticket_show(ticket: str) -> str:
    ticket = _ticket_id(ticket)
    path = _ticket_path(_require_home(), ticket)
    if not path.is_file():
        return _dump({"ticket": ticket, "file": None, "history": "none"})
    return f"file: {path}\n{path.read_text(encoding='utf-8')}"


def report_add(project: str, ticket: str, kind: str, source: str | None) -> dict[str, Any]:
    root = _require_home()
    _load_project(root, project)
    ticket = _ticket_id(ticket)
    if not REPORT_KIND.fullmatch(kind):
        raise ProjectsError(f"report kind must be a lowercase word: {kind!r}")
    text = Path(source).expanduser().read_text(encoding="utf-8") if source else sys.stdin.read()
    if not text.strip():
        raise ProjectsError("the report is empty")
    reports = _project_dir(root, project) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = _ticket_path(root, ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(path):
        stem = f"{_now()[:10]}-{ticket}-{kind}"
        target = reports / f"{stem}.md"
        number = 2
        while target.exists():
            target = reports / f"{stem}-{number}.md"
            number += 1
        _atomic_write(target, text if text.endswith("\n") else f"{text}\n")
        meta, body = _load_ticket(path, ticket)
        meta["reports"].append({"path": str(target), "kind": kind, "project": project, "at": _now()})
        if project not in meta["projects"]:
            meta["projects"].append(project)
        _save_ticket(path, meta, _event(body, f"{kind} report: {target}"))
    return {"ticket": ticket, "project": project, "report": str(target)}


def status(project: str | None) -> dict[str, Any]:
    root = _require_home()
    if project:
        _load_project(root, project)
    now = datetime.now(timezone.utc)
    tickets = []
    for path in sorted((root / "tickets").glob("*.md")):
        meta, body = _load_ticket(path, path.stem)
        if project and project not in meta["projects"]:
            continue
        taken = []
        for entry in meta["taken"]:
            # A chat that died never releases its record, so the age tells a stale one apart.
            try:
                since = datetime.strptime(entry["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                hours: float | None = round((now - since).total_seconds() / 3600, 1)
            except (KeyError, TypeError, ValueError):
                hours = None
            taken.append({
                **{key: entry.get(key) for key in ("title", "host", "workflow", "since", "id")},
                "hours": hours,
            })
        events = [line[2:] for line in body.splitlines() if line.startswith("- ")]
        tickets.append({
            "ticket": meta.get("ticket", path.stem),
            "projects": meta["projects"],
            "taken": taken,
            "pr": meta["links"].get("pr"),
            "last_report": meta["reports"][-1]["path"] if meta["reports"] else None,
            "last_event": events[-1] if events else None,
            "file": str(path),
        })
    import project_watch

    waiting = project_watch.events(project, False)
    return {"home": str(root), **({"project": project} if project else {"projects": _project_names(root)}),
            "tickets": tickets, "trigger_events": waiting["events"], "queue": waiting["queue"],
            **({"undelivered": waiting["undelivered"]} if waiting.get("undelivered") else {}),
            "watching": waiting["watching"]}


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-projects",
        description="Projects, ticket records, and reports shared by every agent chat on this machine.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create the folder; safe to repeat")

    project = commands.add_parser("project", help="create, show, or list projects").add_subparsers(
        dest="action", required=True)
    create = project.add_parser("create", help="create a project")
    create.add_argument("name")
    create.add_argument("--repository", required=True, help="folder of the repository the project works in")
    create.add_argument("--tracker", choices=TRACKERS, default="files")
    create.add_argument("--scope", action="append", default=[], metavar="KEY=VALUE",
                        help="what the project covers: linear_project=<name> for a Linear project, "
                             "assignee=current_user for every ticket assigned to you; repeatable")
    create.add_argument("--ticket", action="append", default=[], help="a ticket the project covers; repeatable")
    create.add_argument("--no-section", action="store_true",
                        help="do not collect the project's chats in a sidebar section")
    project.add_parser("show", help="print a project").add_argument("name")
    project.add_parser("list", help="print project names")
    section = project.add_parser("section", help="turn the project's sidebar section on or off")
    section.add_argument("name")
    section.add_argument("state", choices=("on", "off"))
    chat = project.add_parser("chat", help="record the calling chat as the chat that manages the project")
    chat.add_argument("name")
    chat.add_argument("--title")
    chat.add_argument("--chat", help="chat id, when the session variable is not set")

    ticket = commands.add_parser("ticket", help="record who works on a ticket and its history").add_subparsers(
        dest="action", required=True)
    take = ticket.add_parser("take", help="record that the calling chat works on a ticket")
    take.add_argument("ticket")
    take.add_argument("--workflow", choices=WORKFLOWS, required=True)
    take.add_argument("--project")
    take.add_argument("--title", help="the chat's title, so that a person can find the chat")
    take.add_argument("--cwd")
    take.add_argument("--chat", help="chat id, when the session variable is not set")
    release = ticket.add_parser("release", help="record that the calling chat stopped working on a ticket")
    release.add_argument("ticket")
    release.add_argument("--result", help="one line: what came out of the work")
    release.add_argument("--pr", help="pull request URL")
    release.add_argument("--chat", help="release the record of another chat, for example a dead one")
    note = ticket.add_parser("note", help="add a line to the ticket's history, for example a decision")
    note.add_argument("ticket")
    note.add_argument("text", nargs="+")
    ticket.add_parser("show", help="print a ticket's record and history").add_argument("ticket")

    report = commands.add_parser("report", help="file a report into a project").add_subparsers(
        dest="action", required=True)
    add = report.add_parser("add", help="save a report; reads standard input without --file")
    add.add_argument("--project", required=True)
    add.add_argument("--ticket", required=True)
    add.add_argument("--kind", required=True, help="review, brainstorm, develop, draft, or another word")
    add.add_argument("--file")

    commands.add_parser("status", help="print every ticket with who holds it and its last event").add_argument(
        "--project")
    import project_watch

    project_watch.add_commands(commands, project)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any] | str:
    if args.command in ("watch", "trigger", "pause", "resume") or getattr(args, "action", None) == "triggers":
        import project_watch

        return project_watch.run(args)
    if args.command == "init":
        return init()
    if args.command == "status":
        return status(args.project)
    if args.command == "project":
        if args.action == "create":
            return project_create(args.name, args.repository, args.tracker, args.scope, args.ticket,
                                  section=not args.no_section)
        if args.action == "section":
            return project_section(args.name, args.state == "on")
        if args.action == "show":
            return project_show(args.name)
        if args.action == "chat":
            return project_chat(args.name, args.title, args.chat)
        return {"projects": _project_names(_require_home())}
    if args.command == "ticket":
        if args.action == "take":
            return ticket_take(args.ticket, args.workflow, args.project, args.title, args.cwd, args.chat)
        if args.action == "release":
            return ticket_release(args.ticket, args.result, args.pr, args.chat)
        if args.action == "note":
            return ticket_note(args.ticket, " ".join(args.text))
        return ticket_show(args.ticket)
    return report_add(args.project, args.ticket, args.kind, args.file)


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        output = run(args)
    except (ProjectsError, OSError) as error:
        print(f"agent-projects: {error}", file=sys.stderr)
        return 2
    print((output if isinstance(output, str) else _dump(output)).rstrip("\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
