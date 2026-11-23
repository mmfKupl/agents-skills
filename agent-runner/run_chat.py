"""Start or continue a full agent chat from a script, and record what it did.

A job from `run_dispatch` is closed on purpose: a fixed tool list, no skills, no
tracker, one attempt. A chat is the application's normal session, with its skills and
connections, kept so that it can be continued after a person answers.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import run_dispatch
import run_manifest as manifest

EFFORTS = ("low", "medium", "high", "xhigh")
BINARIES = {"claude": "AGENT_RUNNER_CLAUDE_BIN", "codex": "AGENT_RUNNER_CODEX_BIN"}
DEFAULT_TIMEOUT_MINUTES = 180.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _binary(vendor: str) -> str:
    found = os.environ.get(BINARIES[vendor]) or shutil.which(vendor)
    if not found:
        raise manifest.ManifestError(f"cannot find `{vendor}`; add it to PATH or set {BINARIES[vendor]}")
    return found


def chat_route(model: str, vendor: str) -> tuple[str, str]:
    """Return the vendor and its model id for a model named any accepted way.

    Unlike a job, a chat does not follow the vendor of the caller: the model's own name
    decides, so that a trigger file means the same thing whoever starts it.
    """
    model_id = manifest._model_id(model)
    if vendor == "auto":
        vendor = "claude" if model_id.startswith("claude-") else "codex"
    return vendor, run_dispatch.vendor_model(model_id, vendor)


def _command(record: dict[str, Any], binary: str, first: bool) -> list[str]:
    model, effort, session = record["model"], record["effort"], record["session"]
    if record["vendor"] == "claude":
        command = [binary, "-p"]
        if first:
            if record["worktree"]:
                command += ["--worktree", record["worktree"]]
            if record["name"]:
                command += ["--name", record["name"]]
        else:
            command += ["--resume", session]
        command += ["--output-format", "json", "--model", model, "--effort", effort]
        if record["unrestricted"]:
            command += ["--permission-mode", "bypassPermissions"]
        return command
    command = [binary, "exec"] if first else [binary, "exec", "resume", session]
    command += ["--json", "--skip-git-repo-check", "-m", model, "-c", f'model_reasoning_effort="{effort}"']
    if first:
        command += ["-C", record["workspace"]]
        if record["worktree"]:
            command.append("--worktree")
    if record["unrestricted"]:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    # Both applications read the prompt from standard input, so its length and quoting do not matter.
    return [*command, "-"] if record["vendor"] == "codex" else command


def _run(command: list[str], cwd: str, prompt: str, stdout: Path, stderr: Path, timeout: float) -> int | None:
    """Run one turn; return its exit code, or None when it was stopped for running too long."""
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True,
        )
        try:
            process.communicate(prompt.encode("utf-8"), timeout=timeout)
            return process.returncode
        except subprocess.TimeoutExpired:
            # The chat starts its own children, so stop the whole process group.
            for sign, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, sign)
                try:
                    process.wait(timeout=wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
            return None


def _worktree_paths(workspace: str) -> set[str]:
    """Return the working copies Git knows for the repository, or nothing outside Git."""
    listing = subprocess.run(
        ["git", "-C", workspace, "worktree", "list", "--porcelain"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    if listing.returncode != 0:
        return set()
    return {line.split(" ", 1)[1] for line in listing.stdout.splitlines() if line.startswith("worktree ")}


def _json_lines(text: str) -> list[dict[str, Any]]:
    values = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _parse_claude(text: str) -> dict[str, Any]:
    events = [event for event in _json_lines(text) if "session_id" in event]
    if not events:
        return {"error": "the Claude run printed no result"}
    last = events[-1]
    usage = last.get("usage") or {}
    cached, write = usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0)
    error = None
    if last.get("is_error"):
        error = f"{last.get('subtype') or 'error'}: {str(last.get('result') or '')[:500]}"
    return {
        "session": last.get("session_id"),
        "result": last.get("result") or "",
        "error": error,
        # As in a job's result, input_tokens counts uncached, cached, and cache-write input together.
        "usage": {
            "input_tokens": usage.get("input_tokens", 0) + cached + write,
            "cached_input_tokens": cached,
            "cache_write_input_tokens": write,
            "output_tokens": usage.get("output_tokens", 0),
        },
        "cost_usd": last.get("total_cost_usd"),
    }


def _parse_codex(text: str) -> dict[str, Any]:
    session, result, error = None, "", None
    usage = dict.fromkeys(
        ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens"), 0)
    events = _json_lines(text)
    for event in events:
        kind, item = event.get("type"), event.get("item") or {}
        if kind == "thread.started":
            session = event.get("thread_id")
        elif kind == "item.completed" and item.get("type") == "agent_message":
            result = item.get("text") or ""
        elif kind == "turn.completed":
            for key in usage:
                usage[key] += (event.get("usage") or {}).get(key, 0)
        elif kind in ("turn.failed", "error"):
            detail = event.get("error") or event.get("message") or kind
            error = str(detail.get("message") if isinstance(detail, dict) else detail)[:500]
    if not events:
        error = "the Codex run printed no events"
    return {"session": session, "result": result, "error": error, "usage": usage, "cost_usd": None}


def _save(path: Path, record: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(temporary, path)


def _turn(run_dir: Path, record: dict[str, Any], prompt: str, timeout_minutes: float) -> tuple[int, str]:
    record_path = run_dir / "chat.yaml"
    with (run_dir / "chat.lock").open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise manifest.ManifestError(f"a turn of this chat is still running: {run_dir}") from exc
        number = len(record["turns"]) + 1
        first = record["session"] is None
        files = {name: run_dir / f"{name}-{number}.{suffix}" for name, suffix in (
            ("prompt", "md"), ("result", "md"), ("output", "jsonl"), ("stderr", "log"))}
        files["prompt"].write_text(prompt, encoding="utf-8")
        turn: dict[str, Any] = {"number": number, "started": _now(), "status": "running",
                                **{name: str(path) for name, path in files.items()}}
        record["turns"].append(turn)
        record["status"] = "running"
        _save(record_path, record)

        command = _command(record, _binary(record["vendor"]), first)
        managed = first and record["vendor"] == "codex" and bool(record["worktree"])
        before = _worktree_paths(record["workspace"]) if managed else set()
        code = _run(command, record["cwd"] if not first else record["workspace"], prompt,
                    files["output"], files["stderr"], timeout_minutes * 60)
        if managed:
            # Codex names its managed working copy itself and does not print the path, so
            # it is the one that appeared during the turn. With none or several, later
            # turns stay in the repository folder.
            made = sorted(_worktree_paths(record["workspace"]) - before)
            if len(made) == 1 and Path(made[0]).is_dir():
                record["cwd"] = made[0]
        text = files["output"].read_text(encoding="utf-8", errors="replace")
        parsed = _parse_claude(text) if record["vendor"] == "claude" else _parse_codex(text)
        if code is None:
            status, error = "timed_out", f"stopped after {timeout_minutes:g} minutes"
        elif code != 0 or parsed["error"]:
            tail = files["stderr"].read_text(encoding="utf-8", errors="replace").strip()[-500:]
            status, error = "failed", parsed["error"] or f"exit code {code}: {tail}"
        else:
            status, error = "completed", None
        files["result"].write_text(parsed.get("result") or "", encoding="utf-8")
        if parsed.get("session"):
            record["session"] = parsed["session"]
        if first and record["vendor"] == "claude" and record["worktree"]:
            # Claude Code keeps a session with the folder it ran in, so later turns run in
            # the working copy it made, when the first turn got far enough to make it.
            copy = Path(record["workspace"]) / ".claude" / "worktrees" / record["worktree"]
            if copy.is_dir():
                record["cwd"] = str(copy)
        turn.update(finished=_now(), status=status, exit_code=code, usage=parsed.get("usage"),
                    cost_usd=parsed.get("cost_usd"), error=error)
        record["status"] = status
        _save(record_path, record)
    summary = {
        "chat": str(run_dir), "vendor": record["vendor"], "model": record["model"],
        "effort": record["effort"], "session": record["session"], "turn": number,
        "status": status, "result": turn["result"], "usage": turn["usage"],
        "cost_usd": turn["cost_usd"], "error": error, "report": parsed.get("result") or "",
    }
    return (0 if status == "completed" else 1), yaml.safe_dump(summary, sort_keys=False, allow_unicode=True)


def start(
    *, workspace: str, model: str, effort: str, prompt_file: str, vendor: str = "auto",
    run_dir: str | None = None, name: str | None = None, worktree: str | None = None,
    unrestricted: bool = False, timeout_minutes: float = DEFAULT_TIMEOUT_MINUTES,
) -> tuple[int, str]:
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise manifest.ManifestError("the prompt is empty")
    if effort not in EFFORTS:
        raise manifest.ManifestError(f"unsupported effort: {effort!r}; use one of {', '.join(EFFORTS)}")
    folder = Path(workspace).expanduser().resolve()
    if not folder.is_dir():
        raise manifest.ManifestError(f"workspace is not a folder: {folder}")
    chosen_vendor, chosen_model = chat_route(model, vendor)
    target = Path(run_dir).expanduser().resolve() if run_dir else Path(tempfile.mkdtemp(prefix="agent-chat-"))
    target.mkdir(parents=True, exist_ok=True)
    if (target / "chat.yaml").exists():
        raise manifest.ManifestError(f"{target} already holds a chat; continue it with chat-resume")
    record: dict[str, Any] = {
        "kind": "agent-chat", "schema_version": 1, "vendor": chosen_vendor, "model": chosen_model,
        "effort": effort, "workspace": str(folder), "cwd": str(folder), "worktree": worktree,
        "name": name, "unrestricted": unrestricted, "session": None, "status": "running",
        "created": _now(), "turns": [],
    }
    return _turn(target, record, prompt, timeout_minutes)


def resume(*, run_dir: str, prompt_file: str, timeout_minutes: float = DEFAULT_TIMEOUT_MINUTES) -> tuple[int, str]:
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise manifest.ManifestError("the prompt is empty")
    target = Path(run_dir).expanduser().resolve()
    record = manifest._load_yaml(target / "chat.yaml", "chat record")
    if record.get("kind") != "agent-chat":
        raise manifest.ManifestError(f"{target / 'chat.yaml'} is not a chat record")
    if not record.get("session"):
        raise manifest.ManifestError("this chat has no session to continue: its first turn did not start one")
    return _turn(target, record, prompt, timeout_minutes)
