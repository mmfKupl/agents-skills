#!/usr/bin/env python3
"""One-shot foreground runner for a single Codex agent task."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import fcntl
import hashlib
import json
import math
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator

import yaml
from openai_codex import (
    ApprovalMode,
    AsyncCodex,
    CodexConfig,
    Sandbox,
    __version__ as CODEX_SDK_VERSION,
)


RUNNER_VERSION = "1.6.0"
CLEANUP_GRACE_SECONDS = 5.0
SIGNAL_POLL_SECONDS = 0.1
HEARTBEAT_INTERVAL_SECONDS = 5.0

FIXED_DEVELOPER_INSTRUCTIONS = """\
Runner constraints (these override any conflicting task-specific instruction):
- Work only on the assigned task in the configured workspace.
- Do not create subagents, delegate work, or orchestrate other agents.
- Do not create or modify runner, planning, lock, run, or orchestration files.
- Return exactly one object matching the required structured output schema.
- Use status "checkpoint" when asked to stop for context rotation; summarize durable
  progress precisely so a fresh worker can continue without dialogue history.
"""

CHECKPOINT_STEER = """\
Stop new work now. Finish any operation that cannot safely be left half-applied, then
return the required structured output with status "checkpoint". Put durable progress,
important decisions, and exact continuation guidance in the structured fields.
"""

WORKER_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "summary",
        "report",
        "completed",
        "remaining",
        "changed_files",
        "artifacts",
        "validation",
        "warnings",
        "questions",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["completed", "checkpoint", "blocked"]},
        "summary": {"type": "string"},
        "report": {"type": "string"},
        "completed": {"type": "array", "items": {"type": "string"}},
        "remaining": {"type": "array", "items": {"type": "string"}},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "artifacts": {"type": "array", "items": {"type": "string"}},
        "validation": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["command", "status", "summary"],
                "properties": {
                    "command": {"type": "string"},
                    "status": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
}

TERMINAL_STATUSES = {
    "completed",
    "blocked",
    "needs_approval",
    "failed",
    "interrupted",
    "worktree_locked",
    "invalid_task",
    "context_exhausted",
}


class TaskValidationError(ValueError):
    """Raised when a task is not a strict agent-task v2 document."""


class RunnerInterrupted(Exception):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise TaskValidationError("mapping keys must be scalar values") from exc
        if duplicate:
            raise TaskValidationError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _execution_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}-{os.getpid()}-{uuid.uuid4().hex[:12]}"


def _require_mapping(value: Any, location: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TaskValidationError(f"{location} must be a mapping")
    non_string = [key for key in value if not isinstance(key, str)]
    if non_string:
        raise TaskValidationError(f"{location} keys must be strings")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise TaskValidationError(f"unknown {location} key(s): {', '.join(unknown)}")
    missing = sorted(allowed - set(value))
    if missing:
        raise TaskValidationError(f"missing {location} key(s): {', '.join(missing)}")
    return value


def _require_optional_mapping(
    value: Any, location: str, required: set[str], optional: set[str]
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TaskValidationError(f"{location} must be a mapping")
    non_string = [key for key in value if not isinstance(key, str)]
    if non_string:
        raise TaskValidationError(f"{location} keys must be strings")
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise TaskValidationError(f"unknown {location} key(s): {', '.join(unknown)}")
    missing = sorted(required - set(value))
    if missing:
        raise TaskValidationError(f"missing {location} key(s): {', '.join(missing)}")
    return value


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskValidationError(f"{location} must be a nonempty string")
    return value


def _positive_number(value: Any, location: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TaskValidationError(f"{location} must be a positive number")
    if not math.isfinite(float(value)) or value <= 0:
        raise TaskValidationError(f"{location} must be a positive finite number")
    return value


def _strict_positive_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TaskValidationError(f"{location} must be a positive integer")
    return value


def parse_task(raw: bytes, task_path: Path) -> dict[str, Any]:
    """Parse and validate an immutable agent-task v2 byte sequence."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TaskValidationError("task must be UTF-8 YAML") from exc
    try:
        document = yaml.load(text, Loader=UniqueKeyLoader)
    except TaskValidationError:
        raise
    except yaml.YAMLError as exc:
        raise TaskValidationError(f"invalid YAML: {exc}") from exc

    root = _require_mapping(
        document,
        "task",
        {"kind", "schema_version", "job", "workspace", "agent", "permissions", "supervision"},
    )
    if root["kind"] != "agent-task":
        raise TaskValidationError("kind must be 'agent-task'")
    if type(root["schema_version"]) is not int or root["schema_version"] != 2:
        raise TaskValidationError("schema_version must be integer 2")

    job = _require_mapping(root["job"], "job", {"id", "prompt"})
    _nonempty_string(job["id"], "job.id")
    _nonempty_string(job["prompt"], "job.prompt")

    workspace = _require_mapping(root["workspace"], "workspace", {"cwd"})
    cwd_text = _nonempty_string(workspace["cwd"], "workspace.cwd")
    cwd = Path(cwd_text)
    if not cwd.is_absolute():
        raise TaskValidationError("workspace.cwd must be absolute")
    if not cwd.is_dir():
        raise TaskValidationError("workspace.cwd must be an existing directory")

    agent = _require_optional_mapping(
        root["agent"],
        "agent",
        {"model", "reasoning_effort"},
        {"developer_instructions"},
    )
    _nonempty_string(agent["model"], "agent.model")
    _nonempty_string(agent["reasoning_effort"], "agent.reasoning_effort")
    if "developer_instructions" in agent and not isinstance(agent["developer_instructions"], str):
        raise TaskValidationError("agent.developer_instructions must be a string")

    permissions = _require_mapping(
        root["permissions"],
        "permissions",
        {"sandbox_mode", "approval_policy", "network_access"},
    )
    if permissions["sandbox_mode"] not in {
        "read_only",
        "workspace_write",
        "danger_full_access",
    }:
        raise TaskValidationError(
            "permissions.sandbox_mode must be read_only, workspace_write, or danger_full_access"
        )
    if permissions["approval_policy"] != "never":
        raise TaskValidationError("permissions.approval_policy must be 'never' in v2")
    if not isinstance(permissions["network_access"], bool):
        raise TaskValidationError("permissions.network_access must be a boolean")
    sandbox_mode = permissions["sandbox_mode"]
    network_access = permissions["network_access"]
    if sandbox_mode in {"read_only", "workspace_write"} and network_access:
        raise TaskValidationError(
            f"{sandbox_mode} with network_access=true is not supported by the public SDK preset"
        )
    if sandbox_mode == "danger_full_access" and not network_access:
        raise TaskValidationError(
            "danger_full_access cannot enforce network_access=false; set it to true explicitly"
        )

    supervision = _require_mapping(
        root["supervision"],
        "supervision",
        {"context", "max_attempts"},
    )
    context = _require_mapping(
        supervision["context"],
        "supervision.context",
        {"soft_limit_tokens", "hard_limit_tokens", "checkpoint_grace_seconds"},
    )
    soft = _strict_positive_int(context["soft_limit_tokens"], "soft_limit_tokens")
    hard = _strict_positive_int(context["hard_limit_tokens"], "hard_limit_tokens")
    _positive_number(context["checkpoint_grace_seconds"], "checkpoint_grace_seconds")
    if soft >= hard:
        raise TaskValidationError("context limits must satisfy 0 < soft < hard")
    if not 10 * hard <= 100 * (hard - soft) <= 15 * hard:
        raise TaskValidationError(
            "soft context token limit must be 10% to 15% below hard"
        )
    _strict_positive_int(supervision["max_attempts"], "supervision.max_attempts")

    # Preserve the validated task values exactly; task_path is accepted for a stable API
    # and intentionally is not reread or rewritten.
    _ = task_path
    return root


def validate_worker_output(value: Any) -> dict[str, Any]:
    required = {
        "status",
        "summary",
        "report",
        "completed",
        "remaining",
        "changed_files",
        "artifacts",
        "validation",
        "warnings",
        "questions",
    }
    output = _require_mapping(value, "worker output", required)
    if output["status"] not in {"completed", "checkpoint", "blocked"}:
        raise TaskValidationError("worker output status is invalid")
    for key in ("summary", "report"):
        if not isinstance(output[key], str):
            raise TaskValidationError(f"worker output {key} must be a string")
    for key in (
        "completed",
        "remaining",
        "changed_files",
        "artifacts",
        "warnings",
        "questions",
    ):
        if not isinstance(output[key], list) or any(not isinstance(item, str) for item in output[key]):
            raise TaskValidationError(f"worker output {key} must be a list of strings")
    if not isinstance(output["validation"], list):
        raise TaskValidationError("worker output validation must be a list")
    for index, item in enumerate(output["validation"]):
        checked = _require_mapping(
            item, f"worker output validation[{index}]", {"command", "status", "summary"}
        )
        if any(not isinstance(checked[key], str) for key in checked):
            raise TaskValidationError(
                f"worker output validation[{index}] values must be strings"
            )
    return output


class AtomicResultWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, result: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                yaml.safe_dump(
                    result,
                    handle,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temp_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    temp_path.unlink()


def _initial_result(execution_id: str, task_path: Path, task_sha256: str | None) -> dict[str, Any]:
    started_at = _utc_now()
    return {
        "kind": "agent-result",
        "schema_version": 1,
        "execution": {
            "id": execution_id,
            "status": "running",
            "pid": os.getpid(),
            "started_at": started_at,
            "finished_at": None,
            "heartbeat_at": started_at,
        },
        "task": {"path": str(task_path), "sha256": task_sha256, "job_id": None},
        "runner": {
            "version": RUNNER_VERSION,
            "sdk_version": CODEX_SDK_VERSION,
            "sdk_package": "openai-codex",
            "runtime_package": "openai-codex-cli-bin==0.147.0",
            "python_version": platform.python_version(),
            "pyyaml_version": yaml.__version__,
        },
        "effective_configuration": None,
        "attempts": [],
        "usage": _empty_breakdown(),
        "outcome": None,
        "approval": {
            "policy": "never",
            "mode": "deny_all",
            "requested": False,
        },
        "error": None,
    }


def _touch(result: dict[str, Any], writer: AtomicResultWriter) -> None:
    result["execution"]["heartbeat_at"] = _utc_now()
    writer.write(result)


def _error(kind: str, message: str) -> dict[str, str]:
    return {"type": kind, "message": message}


def _finalize(
    result: dict[str, Any],
    writer: AtomicResultWriter,
    status: str,
    *,
    outcome: dict[str, Any] | None = None,
    error: dict[str, str] | None = None,
) -> None:
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"invalid terminal status: {status}")
    finished_at = _utc_now()
    result["execution"].update(
        {"status": status, "finished_at": finished_at, "heartbeat_at": finished_at}
    )
    result["outcome"] = outcome
    result["error"] = error
    writer.write(result)


def _empty_breakdown() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }


def _breakdown(value: Any) -> dict[str, int]:
    result = _empty_breakdown()
    if value is None:
        return result
    for key in result:
        raw = getattr(value, key, None)
        if raw is None and isinstance(value, dict):
            raw = value.get(key)
            if raw is None:
                camel = "".join(
                    part if index == 0 else part.title()
                    for index, part in enumerate(key.split("_"))
                )
                raw = value.get(camel)
        if isinstance(raw, int) and not isinstance(raw, bool):
            result[key] = raw
    return result


def _usage(value: Any) -> dict[str, Any]:
    if value is None:
        return {"last": _empty_breakdown(), "total": _empty_breakdown(), "model_context_window": None}
    if isinstance(value, dict):
        last = value.get("last")
        total = value.get("total")
        window = value.get("model_context_window", value.get("modelContextWindow"))
    else:
        last = getattr(value, "last", None)
        total = getattr(value, "total", None)
        window = getattr(value, "model_context_window", None)
    return {
        "last": _breakdown(last),
        "total": _breakdown(total),
        "model_context_window": window if isinstance(window, int) and window > 0 else None,
    }


def _aggregate_usage(result: dict[str, Any]) -> None:
    aggregate = _empty_breakdown()
    for attempt in result["attempts"]:
        total = attempt.get("token_usage", {}).get("total", {})
        for key in aggregate:
            value = total.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                aggregate[key] += value
    result["usage"] = aggregate


def _sdk_error_text(value: Any) -> str | None:
    if value is None:
        return None
    message = getattr(value, "message", None)
    if isinstance(message, str):
        return message
    if isinstance(value, dict) and isinstance(value.get("message"), str):
        return value["message"]
    return str(value)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _agent_message_from_item(payload: Any) -> str | None:
    item = getattr(payload, "item", None)
    item = getattr(item, "root", item)
    if item is None or getattr(item, "type", None) != "agentMessage":
        return None
    phase = _enum_value(getattr(item, "phase", None))
    if phase not in {None, "final_answer"}:
        return None
    text = getattr(item, "text", None)
    return text if isinstance(text, str) else None


def _worker_prompt(task: dict[str, Any], attempt_number: int, carry: dict[str, Any] | None) -> str:
    prompt = task["job"]["prompt"]
    sections = [
        f"Assigned task (job {task['job']['id']}), attempt {attempt_number}:\n{prompt}",
        "Return only the required structured output object when done or blocked.",
    ]
    if carry is not None:
        sections.append(
            "A previous ephemeral worker stopped. Continue from only this structured handoff; "
            "do not infer or request its dialogue history:\n" + json.dumps(carry, ensure_ascii=False)
        )
    return "\n\n".join(sections)


def _developer_instructions(task: dict[str, Any]) -> str:
    custom = task["agent"].get("developer_instructions", "")
    if custom:
        return f"{custom.rstrip()}\n\n{FIXED_DEVELOPER_INSTRUCTIONS}"
    return FIXED_DEVELOPER_INSTRUCTIONS


def _sandbox(task: dict[str, Any]) -> Sandbox:
    return {
        "read_only": Sandbox.read_only,
        "workspace_write": Sandbox.workspace_write,
        "danger_full_access": Sandbox.full_access,
    }[task["permissions"]["sandbox_mode"]]


def _config_overrides(task: dict[str, Any]) -> tuple[str, ...]:
    _ = task
    return ("agents.enabled=false",)


@dataclass
class SignalState:
    triggered: str | None = None


@contextlib.contextmanager
def _capture_signals(state: SignalState) -> Iterator[None]:
    if not hasattr(signal, "SIGTERM"):
        yield
        return
    previous: dict[signal.Signals, Any] = {}

    def handler(signum: int, _frame: Any) -> None:
        if state.triggered is None:
            state.triggered = signal.Signals(signum).name

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, handler)
    except ValueError:
        yield
        return
    try:
        yield
    finally:
        for sig, old_handler in previous.items():
            signal.signal(sig, old_handler)


async def _await_controlled(awaitable: Awaitable[Any], signals: SignalState) -> Any:
    task = asyncio.ensure_future(awaitable)
    try:
        while not task.done():
            if signals.triggered:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise RunnerInterrupted(signals.triggered)
            await asyncio.wait({task}, timeout=SIGNAL_POLL_SECONDS)
        return await task
    except BaseException:
        if not task.done():
            task.cancel()
        raise


async def _bounded_call(awaitable: Awaitable[Any], timeout: float = CLEANUP_GRACE_SECONDS) -> Any:
    return await asyncio.wait_for(awaitable, timeout=max(0.01, timeout))


@dataclass
class AttemptResult:
    action: str
    outcome: dict[str, Any] | None = None
    carry: dict[str, Any] | None = None
    error: dict[str, str] | None = None


async def _run_attempt(
    codex: Any,
    task: dict[str, Any],
    result: dict[str, Any],
    writer: AtomicResultWriter,
    attempt_number: int,
    carry: dict[str, Any] | None,
    signals: SignalState,
) -> AttemptResult:
    sandbox = _sandbox(task)
    cwd = task["workspace"]["cwd"]
    model = task["agent"]["model"]
    attempt = {
        "number": attempt_number,
        "thread_id": None,
        "turn_id": None,
        "started_at": _utc_now(),
        "finished_at": None,
        "status": "starting",
        "context_peak_tokens": 0,
        "context_peak_percent": 0.0,
        "token_usage": _usage(None),
        "checkpoint": None,
    }
    result["attempts"].append(attempt)
    _touch(result, writer)

    try:
        thread = await _await_controlled(
            codex.thread_start(
                approval_mode=ApprovalMode.deny_all,
                config=None,
                cwd=cwd,
                developer_instructions=_developer_instructions(task),
                ephemeral=True,
                model=model,
                sandbox=sandbox,
            ),
            signals,
        )
        attempt["thread_id"] = thread.id
        turn = await _await_controlled(
            thread.turn(
                _worker_prompt(task, attempt_number, carry),
                approval_mode=ApprovalMode.deny_all,
                cwd=cwd,
                effort=task["agent"]["reasoning_effort"],
                model=model,
                output_schema=WORKER_OUTPUT_SCHEMA,
                sandbox=sandbox,
            ),
            signals,
        )
    except RunnerInterrupted:
        attempt.update({"finished_at": _utc_now(), "status": "interrupted"})
        _touch(result, writer)
        raise
    except Exception:
        attempt.update({"finished_at": _utc_now(), "status": "failed"})
        _touch(result, writer)
        raise
    attempt["turn_id"] = turn.id
    attempt["status"] = "running"
    _touch(result, writer)

    soft = task["supervision"]["context"]["soft_limit_tokens"]
    hard = task["supervision"]["context"]["hard_limit_tokens"]
    checkpoint_grace = float(task["supervision"]["context"]["checkpoint_grace_seconds"])
    soft_steered_at: float | None = None
    interrupt_reason: str | None = None
    cleanup_deadline: float | None = None
    completed_payload: Any = None
    final_response: str | None = None
    partial_chunks: list[str] = []
    stream = turn.stream()
    next_event: asyncio.Task[Any] | None = None
    stream_error: Exception | None = None
    last_persisted_at = time.monotonic()

    def persist_event(force: bool = False) -> None:
        nonlocal last_persisted_at
        now = time.monotonic()
        if force or now - last_persisted_at >= HEARTBEAT_INTERVAL_SECONDS:
            _aggregate_usage(result)
            _touch(result, writer)
            last_persisted_at = now

    async def request_interrupt(reason: str) -> None:
        nonlocal interrupt_reason, cleanup_deadline
        if interrupt_reason is not None:
            if reason == "signal" and interrupt_reason == "context":
                interrupt_reason = reason
                cleanup_deadline = time.monotonic() + CLEANUP_GRACE_SECONDS
            return
        interrupt_reason = reason
        if reason == "signal":
            cleanup_deadline = time.monotonic() + CLEANUP_GRACE_SECONDS
        with contextlib.suppress(Exception):
            await _bounded_call(turn.interrupt())

    try:
        while completed_payload is None:
            now = time.monotonic()
            if signals.triggered:
                await request_interrupt("signal")
            elif soft_steered_at is not None and now - soft_steered_at >= checkpoint_grace:
                await request_interrupt("context")

            if cleanup_deadline is not None and now >= cleanup_deadline:
                break

            if next_event is None:
                next_event = asyncio.create_task(anext(stream))

            wait_seconds = SIGNAL_POLL_SECONDS
            if soft_steered_at is not None and interrupt_reason is None:
                wait_seconds = min(
                    wait_seconds,
                    max(0.0, soft_steered_at + checkpoint_grace - time.monotonic()),
                )
            if cleanup_deadline is not None:
                wait_seconds = min(
                    wait_seconds, max(0.0, cleanup_deadline - time.monotonic())
                )
            done, _ = await asyncio.wait({next_event}, timeout=wait_seconds)
            if not done:
                continue
            try:
                event = next_event.result()
            except StopAsyncIteration:
                break
            finally:
                next_event = None

            method = getattr(event, "method", "")
            payload = getattr(event, "payload", None)
            if method == "item/agentMessage/delta":
                delta = getattr(payload, "delta", None)
                if isinstance(delta, str):
                    partial_chunks.append(delta)
            elif method == "item/completed":
                message = _agent_message_from_item(payload)
                if message is not None:
                    final_response = message
            elif method == "thread/tokenUsage/updated":
                usage = _usage(getattr(payload, "token_usage", None))
                attempt["token_usage"] = usage
                last_total = usage["last"]["total_tokens"]
                attempt["context_peak_tokens"] = max(
                    attempt["context_peak_tokens"], last_total
                )
                window = usage["model_context_window"]
                if window:
                    percent = last_total * 100.0 / window
                    attempt["context_peak_percent"] = round(
                        max(attempt["context_peak_percent"], percent), 4
                    )
                if last_total >= soft and soft_steered_at is None:
                    soft_steered_at = time.monotonic()
                    with contextlib.suppress(Exception):
                        await _bounded_call(turn.steer(CHECKPOINT_STEER))
                if last_total >= hard:
                    await request_interrupt("context")
            elif method == "turn/completed":
                completed_payload = payload
            persist_event(
                method
                in {"item/completed", "thread/tokenUsage/updated", "turn/completed"}
            )
    except Exception as exc:
        stream_error = exc
    finally:
        if next_event is not None and not next_event.done():
            next_event.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await next_event
        with contextlib.suppress(RuntimeError, Exception):
            await stream.aclose()

    attempt["finished_at"] = _utc_now()
    turn_status = None
    turn_error = None
    if completed_payload is not None:
        completed_turn = getattr(completed_payload, "turn", None)
        turn_status = _enum_value(getattr(completed_turn, "status", None))
        turn_error = _sdk_error_text(getattr(completed_turn, "error", None))

    if stream_error is not None:
        attempt["status"] = "failed"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult(
            "failed", error=_error(type(stream_error).__name__, str(stream_error))
        )

    if interrupt_reason == "signal":
        attempt["status"] = "interrupted"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult(
            "interrupted",
            error=_error("signal", f"received {signals.triggered or 'termination signal'}"),
        )
    parsed_output: dict[str, Any] | None = None
    output_error: Exception | None = None
    if final_response is not None:
        try:
            parsed_output = validate_worker_output(json.loads(final_response))
        except (json.JSONDecodeError, TaskValidationError) as exc:
            output_error = exc

    if completed_payload is None:
        attempt["status"] = "failed"
        message = "turn stream ended without a terminal turn/completed event"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult("failed", error=_error("worker_turn", message))

    if turn_status == "failed":
        attempt["status"] = "failed"
        message = turn_error or "Codex turn failed"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult("failed", error=_error("worker_turn", message))

    if turn_status == "interrupted":
        if interrupt_reason == "context":
            attempt["status"] = "interrupted_for_context"
            if parsed_output is not None and parsed_output["status"] == "checkpoint":
                attempt["checkpoint"] = parsed_output
                carry = {"kind": "structured_checkpoint", "output": parsed_output}
            else:
                carry = {
                    "kind": "fallback_partial_agent_output",
                    "text": "".join(partial_chunks).strip(),
                    "note": (
                        "The prior turn crossed a context boundary before a valid "
                        "structured checkpoint."
                    ),
                }
                attempt["checkpoint"] = carry
            _aggregate_usage(result)
            _touch(result, writer)
            return AttemptResult("rotate", carry=carry)
        attempt["status"] = "interrupted"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult(
            "interrupted",
            error=_error("worker_turn", "Codex turn was unexpectedly interrupted"),
        )

    if turn_status != "completed":
        attempt["status"] = "failed"
        message = f"Codex turn ended with unexpected status: {turn_status!r}"
        _aggregate_usage(result)
        _touch(result, writer)
        return AttemptResult("failed", error=_error("worker_turn", message))

    if parsed_output is not None:
        attempt["checkpoint"] = parsed_output if parsed_output["status"] == "checkpoint" else None
        attempt["status"] = parsed_output["status"]
        _aggregate_usage(result)
        _touch(result, writer)
        if parsed_output["status"] == "completed":
            return AttemptResult("completed", outcome=parsed_output)
        if parsed_output["status"] == "blocked":
            return AttemptResult("blocked", outcome=parsed_output)
        return AttemptResult("rotate", carry={"kind": "structured_checkpoint", "output": parsed_output})

    if output_error is not None:
        attempt["status"] = "failed"
        message = f"invalid structured worker output: {output_error}"
    else:
        attempt["status"] = "failed"
        message = "Codex turn completed without structured worker output"
    _aggregate_usage(result)
    _touch(result, writer)
    return AttemptResult("failed", error=_error("worker_turn", message))


async def _execute_sdk(
    task: dict[str, Any],
    result: dict[str, Any],
    writer: AtomicResultWriter,
    signals: SignalState,
    sdk_factory: Callable[[CodexConfig], Any],
) -> AttemptResult:
    codex: Any = None
    entered = False
    carry: dict[str, Any] | None = None
    try:
        config = CodexConfig(
            config_overrides=_config_overrides(task), cwd=task["workspace"]["cwd"]
        )
        codex = sdk_factory(config)
        await _await_controlled(codex.__aenter__(), signals)
        entered = True
        for attempt_number in range(1, task["supervision"]["max_attempts"] + 1):
            attempt_result = await _run_attempt(
                codex,
                task,
                result,
                writer,
                attempt_number,
                carry,
                signals,
            )
            if attempt_result.action != "rotate":
                return attempt_result
            carry = attempt_result.carry
        return AttemptResult(
            "context_exhausted",
            error=_error("context_exhausted", "maximum fresh-context attempts exhausted"),
        )
    except RunnerInterrupted as exc:
        return AttemptResult("interrupted", error=_error("signal", f"received {exc}"))
    except Exception as exc:
        return AttemptResult("failed", error=_error(type(exc).__name__, str(exc)))
    finally:
        # close() is safe after partial initialization and is the documented owner cleanup.
        if codex is not None and (entered or hasattr(codex, "close")):
            with contextlib.suppress(Exception):
                await _bounded_call(codex.close())


class WorktreeLock:
    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.handle: Any = None
        self.key_path: Path | None = None

    def _canonical_root(self) -> Path:
        canonical_cwd = Path(self.cwd).resolve()
        try:
            completed = subprocess.run(
                ["git", "-C", str(canonical_cwd), "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            root = Path(completed.stdout.strip()).resolve()
            if root.is_dir():
                return root
        except (OSError, subprocess.SubprocessError):
            pass
        return canonical_cwd

    def acquire(self) -> bool:
        root = self._canonical_root()
        digest = hashlib.sha256(os.fsencode(root)).hexdigest()
        lock_dir = Path(tempfile.gettempdir()) / "codex-agent-runner-locks"
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.key_path = lock_dir / f"{digest}.lock"
        self.handle = self.key_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            self.handle = None
            return False
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} cwd={root}\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())
        return True

    def release(self) -> None:
        if self.handle is None:
            return
        with contextlib.suppress(OSError):
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None

    def __enter__(self) -> "WorktreeLock":
        if not self.acquire():
            raise BlockingIOError("worktree is locked by another cooperating runner")
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.release()


@dataclass(frozen=True)
class InvocationResult:
    path: Path
    status: str


def _continue_invocation(
    task_path: Path,
    task_bytes: bytes | None,
    read_error: OSError | None,
    result_path: Path,
    result: dict[str, Any],
    writer: AtomicResultWriter,
    signal_state: SignalState,
    sdk_factory: Callable[[CodexConfig], Any],
) -> InvocationResult:
    if read_error is not None:
        _finalize(
            result,
            writer,
            "invalid_task",
            error=_error(type(read_error).__name__, str(read_error)),
        )
        return InvocationResult(result_path, "invalid_task")

    try:
        task = parse_task(task_bytes or b"", task_path)
    except TaskValidationError as exc:
        _finalize(result, writer, "invalid_task", error=_error("invalid_task", str(exc)))
        return InvocationResult(result_path, "invalid_task")

    result["task"]["job_id"] = task["job"]["id"]
    result["effective_configuration"] = {
        "workspace": {"cwd": task["workspace"]["cwd"]},
        "agent": {
            "model": task["agent"]["model"],
            "reasoning_effort": task["agent"]["reasoning_effort"],
            "developer_instructions": _developer_instructions(task),
        },
        "permissions": dict(task["permissions"]),
        "supervision": dict(task["supervision"]),
        "sdk": {
            "approval_mode": "deny_all",
            "sandbox": _sandbox(task).value,
            "ephemeral_threads": True,
            "config_overrides": list(_config_overrides(task)),
        },
    }
    _touch(result, writer)

    lock: WorktreeLock | None = None
    if task["permissions"]["sandbox_mode"] != "read_only":
        lock = WorktreeLock(task["workspace"]["cwd"])
        try:
            acquired = lock.acquire()
        except OSError as exc:
            _finalize(result, writer, "failed", error=_error(type(exc).__name__, str(exc)))
            return InvocationResult(result_path, "failed")
        if not acquired:
            _finalize(
                result,
                writer,
                "worktree_locked",
                error=_error(
                    "worktree_locked", "another cooperating runner holds the worktree lock"
                ),
            )
            return InvocationResult(result_path, "worktree_locked")

    try:
        try:
            terminal = asyncio.run(
                _execute_sdk(task, result, writer, signal_state, sdk_factory)
            )
        except KeyboardInterrupt:
            terminal = AttemptResult(
                "interrupted", error=_error("signal", "received KeyboardInterrupt")
            )
    finally:
        if lock is not None:
            lock.release()

    status = terminal.action
    if status not in TERMINAL_STATUSES:
        status = "failed"
        terminal.error = _error("runner", f"unexpected terminal action: {terminal.action}")
    _aggregate_usage(result)
    _finalize(
        result,
        writer,
        status,
        outcome=terminal.outcome,
        error=terminal.error,
    )
    return InvocationResult(result_path, status)


def run_invocation(
    task_argument: str,
    *,
    sdk_factory: Callable[[CodexConfig], Any] = AsyncCodex,
    signals: SignalState | None = None,
) -> InvocationResult:
    """Run one task and return its unique result path and terminal status."""
    task_path = Path(os.path.abspath(os.path.expanduser(task_argument)))
    execution_id = _execution_id()
    result_path = task_path.parent / "results" / f"{execution_id}.yaml"
    task_bytes: bytes | None = None
    read_error: OSError | None = None
    try:
        task_bytes = task_path.read_bytes()
    except OSError as exc:
        read_error = exc
    task_sha256 = hashlib.sha256(task_bytes).hexdigest() if task_bytes is not None else None
    result = _initial_result(execution_id, task_path, task_sha256)
    writer = AtomicResultWriter(result_path)
    writer.write(result)
    signal_state = signals or SignalState()
    with _capture_signals(signal_state):
        return _continue_invocation(
            task_path,
            task_bytes,
            read_error,
            result_path,
            result,
            writer,
            signal_state,
            sdk_factory,
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-runner",
        description="Run exactly one immutable agent-task v2 YAML file in the foreground.",
    )
    parser.add_argument("task", help="path to one agent-task v2 YAML file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        invocation = run_invocation(args.task)
    except Exception as exc:
        print(f"agent-runner: unable to create/finalize result: {exc}", file=sys.stderr)
        return 3
    print(invocation.path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
