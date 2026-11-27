"""Dev stands shared by every agent chat on one machine.

A stand is the Docker Compose project that a repository's own script starts for one
worktree, such as UI Bakery's `run-bakery-dev-in-docker`. Several chats start stands on
one machine, and each Angular dev server alone takes gigabytes, so a stand starts only
when the memory is free: `stand take` waits for it, records who started the stand, why,
and until when, and starts it. `stand done` removes it after the work, or only stops it
with `--keep`. The watching service stops and removes the stands that their chats left.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import agent_projects as projects
from agent_projects import ProjectsError

STANDS_FILE = "stands.yaml"
# The script that starts a stand, relative to the root of its worktree.
SCRIPT = Path(".codex/skills/run-bakery-dev-in-docker/scripts/bakery-dev-docker.sh")
# What each service takes, in gigabytes, once it has run for a while: measured on the
# UI Bakery VM on 2026-11-27, with the heap of an Angular dev server capped at `HEAP_MB`.
SERVICE_GB = {"bakery": 4.5, "workbench": 4.5, "back": 1.5, "datasource": 0.5, "chat": 1.0, "automation": 1.5}
DATABASES_GB = 0.5
# Memory left free after a stand starts, for the chats, tests, and the system.
RESERVE_GB = 2.0
# How much memory an Angular dev server of a stand may use, passed to the stand's script:
# half of the repository's 8096. The script reads it once uibakery/uibakery#7711 is in.
HEAP_MB = 4096
HEAP_VARIABLE = "UI_BAKERY_DEV_NODE_HEAP_MB"
# A stand that started this recently has not grown to its size yet, so the memory it
# will take is not counted as taken.
GROWING = timedelta(minutes=10)
# How long `stand take` waits for memory by default: below the ten minutes after which
# a chat's command is stopped.
WAIT_MINUTES = 8
POLL_SECONDS = 30.0
# A stand whose chat is gone is stopped at once and removed after this.
STOPPED_KEPT = timedelta(days=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _path() -> Path:
    return projects._require_home() / STANDS_FILE


def _load(path: Path) -> list[dict[str, Any]]:
    return list((projects._load_mapping(path).get("stands") or []) if path.is_file() else [])


def _save(path: Path, stands: list[dict[str, Any]]) -> None:
    projects._atomic_write(path, projects._dump({"stands": stands}))


def _available_gb() -> float | None:
    """Memory free for new work, from the kernel; None where the machine does not say."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024 / 1024
    except OSError:
        return None
    return None


def _need_gb(services: list[str]) -> float:
    return sum(SERVICE_GB.get(name, 1.0) for name in services) + DATABASES_GB


def _owner() -> dict[str, Any]:
    """The chat that runs this command: the nearest Claude or Codex process above it, so
    that the stand can be told apart from one whose chat has ended."""
    chat = projects._chat()
    pid = os.getppid()
    for _ in range(12):
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            break
        fields = stat.rsplit(")", 1)[1].split()
        if "claude" in command or "codex" in command:
            return {**chat, "pid": pid, "pid_start": fields[19]}
        pid = int(fields[1])
        if pid <= 1:
            break
    return dict(chat)


def _alive(stand: dict[str, Any]) -> bool:
    """Whether the chat that took the stand still runs. Without a process on record the
    answer is yes: nothing says otherwise."""
    pid = stand.get("pid")
    if not pid:
        return True
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except OSError:
        return False
    return fields[19] == str(stand.get("pid_start"))


def _worktree(cwd: str | None) -> Path:
    found = subprocess.run(["git", "-C", cwd or os.getcwd(), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if found.returncode != 0:
        raise ProjectsError(f"{cwd or os.getcwd()} is not inside a git worktree")
    root = Path(found.stdout.strip())
    if not (root / SCRIPT).is_file():
        raise ProjectsError(f"{root} has no {SCRIPT}; this command starts only the stands that script makes")
    return root


def _script(root: Path, *words: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, HEAP_VARIABLE: os.environ.get(HEAP_VARIABLE, str(HEAP_MB))}
    return subprocess.run([str(root / SCRIPT), *words], cwd=root, env=env, text=True,
                          capture_output=capture, stdout=None if capture else sys.stderr)


def _name(root: Path) -> str:
    done = _script(root, "project", capture=True)
    line = next((line for line in done.stdout.splitlines() if line.startswith("Compose project:")), "")
    if done.returncode != 0 or not line:
        raise ProjectsError(f"the stand's script did not name its project: {done.stderr.strip() or done.stdout.strip()}")
    return line.split(":", 1)[1].strip()


def _docker(*words: str) -> list[str]:
    done = subprocess.run(["docker", *words], capture_output=True, text=True)
    return done.stdout.split() if done.returncode == 0 else []


def _running() -> dict[str, str]:
    """The stands that run now, by project name, with the worktree each serves; also
    those that no chat recorded."""
    found: dict[str, str] = {}
    for line in subprocess.run(["docker", "ps", "--format",
                                '{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.project.working_dir"}}'],
                               capture_output=True, text=True).stdout.splitlines():
        name, _, folder = line.partition("\t")
        if name and str(SCRIPT.parent.parent / "assets") in folder:
            found[name] = folder.split("/" + str(SCRIPT.parent.parent), 1)[0]
    return found


def _remove(name: str, keep: bool) -> None:
    """Stop a stand's containers, or remove them with its network and volumes. Works by
    the project's label, so it needs neither the worktree nor its script."""
    label = f"label=com.docker.compose.project={name}"
    containers = _docker("ps", "-aq", "--filter", label)
    if keep:
        if containers:
            _docker("stop", *containers)
        return
    if containers:
        _docker("rm", "-f", *containers)
    networks = _docker("network", "ls", "-q", "--filter", label)
    if networks:
        _docker("network", "rm", *networks)
    volumes = _docker("volume", "ls", "-q", "--filter", label)
    if volumes:
        _docker("volume", "rm", *volumes)


def _free(stands: list[dict[str, Any]], now: datetime) -> float | None:
    """Memory free for a new stand: what the kernel says, less what the stands that are
    still growing will take."""
    available = _available_gb()
    if available is None:
        return None
    growing = sum(_need_gb(stand["services"]) for stand in stands
                  if stand.get("state") == "running" and now - _time(stand["started"]) < GROWING)
    return available - growing


def _view(stand: dict[str, Any], now: datetime) -> dict[str, Any]:
    until = _time(stand["until"])
    return {key: stand[key] for key in ("name", "worktree", "services", "why", "ticket", "state", "started", "until")
            if stand.get(key)} | {"owner": stand.get("id") or "unknown", "chat_running": _alive(stand),
                                   **({"overdue_minutes": int((now - until).total_seconds() // 60)} if now > until else {})}


def stand_list() -> dict[str, Any]:
    path = _path()
    now = _now()
    stands = _load(path)
    known = {stand["name"] for stand in stands}
    free = _available_gb()
    return {"memory_free_gb": round(free, 1) if free is not None else "unknown",
            "stands": [_view(stand, now) for stand in stands],
            "not_recorded": [{"name": name, "worktree": folder} for name, folder in _running().items() if name not in known]}


def _waiting_text(stands: list[dict[str, Any]], need: float, free: float, now: datetime) -> str:
    lines = [f"waiting for memory: the stand needs {need:.1f} GB with {RESERVE_GB:.0f} GB left over, {free:.1f} GB is free"]
    for stand in stands:
        lines.append(f"- {stand['name']}: {stand.get('why') or 'no reason given'}, {', '.join(stand['services'])}, "
                     f"{stand.get('state')}, until {stand['until']}")
    return "\n".join(lines)


def stand_take(services: list[str], why: str, minutes: int, ticket: str | None, wait: int, cwd: str | None) -> dict[str, Any]:
    """Wait until the machine has the memory for the stand, record it, and start it."""
    if not services:
        raise ProjectsError("name the services the check needs, such as: bakery workbench back datasource")
    root = _worktree(cwd)
    name = _name(root)
    path = _path()
    need = _need_gb(services)
    deadline = time.monotonic() + wait * 60
    told = 0.0
    while True:
        with projects._locked(path):
            now = _now()
            stands = _load(path)
            mine = next((stand for stand in stands if stand["name"] == name), None)
            others = [stand for stand in stands if stand["name"] != name]
            free = _free(others, now)
            # A stand already up for this worktree takes its memory already.
            running_here = mine is not None and mine.get("state") == "running"
            if running_here or free is None or free - need >= RESERVE_GB:
                entry = {"name": name, "worktree": str(root), "services": sorted(set(services) | set((mine or {}).get("services") or [])),
                         "why": why, **({"ticket": ticket} if ticket else {}), "state": "running",
                         "started": (mine or {}).get("started") if running_here else _stamp(now),
                         "until": _stamp(now + timedelta(minutes=minutes)), **_owner()}
                _save(path, [*others, entry])
                break
        if time.monotonic() >= deadline:
            raise ProjectsError(_waiting_text(others, need, free, now) + f"\nstill not enough after {wait} minutes: "
                                "run the same command again, or `agent-projects stand list` to see who holds the memory")
        if time.monotonic() - told >= 300 or not told:
            print(_waiting_text(others, need, free, now), file=sys.stderr, flush=True)
            told = time.monotonic()
        time.sleep(POLL_SECONDS)
    done = _script(root, "up", *services)
    if done.returncode != 0:
        raise ProjectsError(f"the stand's script failed to start {', '.join(services)} (exit {done.returncode}); "
                            "the stand stays recorded: `agent-projects stand done` removes it")
    url = _script(root, "url", capture=True).stdout.strip() if "bakery" in services else ""
    return {"stand": name, "services": entry["services"], "until": entry["until"], **({"url": url} if url else {}),
            "next": "run `agent-projects stand done` right after the last check that needs the stand"}


def stand_done(keep: bool, cwd: str | None, name: str | None = None) -> dict[str, Any]:
    """Remove the stand after the work, or only stop it with `keep`."""
    path = _path()
    if name is None:
        root = _worktree(cwd)
        name = _name(root)
        # The repository's own clean-up first: it knows its stand best.
        _script(root, "down" if keep else "cleanup")
    _remove(name, keep)
    with projects._locked(path):
        stands = _load(path)
        kept = [stand for stand in stands if stand["name"] != name]
        if keep:
            kept += [{**stand, "state": "stopped", "stopped": _stamp(_now())} for stand in stands if stand["name"] == name]
        _save(path, kept)
    return {"stand": name, "state": "stopped, its databases kept" if keep else "removed"}


def stand_extend(minutes: int, cwd: str | None) -> dict[str, Any]:
    name = _name(_worktree(cwd))
    path = _path()
    with projects._locked(path):
        stands = _load(path)
        found = next((stand for stand in stands if stand["name"] == name), None)
        if found is None:
            raise ProjectsError(f"{name} is not recorded; start it with `agent-projects stand take`")
        found["until"] = _stamp(_now() + timedelta(minutes=minutes))
        _save(path, stands)
    return {"stand": name, "until": found["until"]}


def sweep(now: datetime | None = None) -> list[str]:
    """Stop the stands that their chats left, and remove them a day later or once their
    worktree is gone. The watching service runs this on every cycle; it returns what it did."""
    path = projects.home() / STANDS_FILE
    if not path.is_file():
        return []
    now = now or _now()
    done: list[str] = []
    with projects._locked(path):
        stands = _load(path)
        kept = []
        for stand in stands:
            gone = not Path(stand["worktree"]).is_dir()
            stopped = stand.get("state") == "stopped"
            if gone or (stopped and now - _time(stand.get("stopped") or stand["until"]) > STOPPED_KEPT):
                _remove(stand["name"], keep=False)
                done.append(f"removed the stand {stand['name']}: " + ("its worktree is gone" if gone else "stopped for a day"))
                continue
            if not stopped and not _alive(stand):
                _remove(stand["name"], keep=True)
                stand = {**stand, "state": "stopped", "stopped": _stamp(now)}
                done.append(f"stopped the stand {stand['name']}: the chat that took it has ended")
            kept.append(stand)
        if kept != stands:
            _save(path, kept)
    # A stand that no chat recorded is left alone while its worktree exists.
    recorded = {stand["name"] for stand in stands}
    for name, folder in _running().items():
        if name not in recorded and folder and not Path(folder).is_dir():
            _remove(name, keep=False)
            done.append(f"removed the stand {name}, which no chat recorded: its worktree is gone")
    return done


def add_commands(commands: Any) -> None:
    stand = commands.add_parser("stand", help="start, list, and remove dev stands shared by the chats on this "
                                              "machine").add_subparsers(dest="action", required=True)
    take = stand.add_parser("take", help="wait for the memory, record the stand, and start it")
    take.add_argument("services", nargs="+", help="the services the check needs, as the stand's script names them")
    take.add_argument("--why", required=True, help="what the stand is for, such as: UIB-123: video of the editor")
    take.add_argument("--minutes", type=int, default=30, help="how long the stand is needed")
    take.add_argument("--ticket")
    take.add_argument("--wait", type=int, default=WAIT_MINUTES, help="how many minutes to wait for memory")
    take.add_argument("--cwd", help="the worktree, when it is not the current folder")
    done = stand.add_parser("done", help="remove the stand after the work; --keep only stops it")
    done.add_argument("--keep", action="store_true", help="stop the containers and keep the databases")
    done.add_argument("--cwd")
    done.add_argument("--name", help="a stand by its name, such as one whose worktree is gone")
    extend = stand.add_parser("extend", help="say that the stand is needed for longer")
    extend.add_argument("--minutes", type=int, required=True)
    extend.add_argument("--cwd")
    stand.add_parser("list", help="print the stands, who took them, why, and until when")


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.action == "take":
        return stand_take(args.services, args.why, args.minutes, args.ticket, args.wait, args.cwd)
    if args.action == "done":
        return stand_done(args.keep, args.cwd, args.name)
    if args.action == "extend":
        return stand_extend(args.minutes, args.cwd)
    return stand_list()
