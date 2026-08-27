#!/usr/bin/env python3
"""Atomically register, reconcile, and finalize a develop-task run manifest."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml


RUN_STATUSES = {"running", "completed", "blocked", "needs_user_input", "stopped"}
FINAL_RUN_STATUSES = RUN_STATUSES - {"running"}
RESULT_STATUSES = {
    "running",
    "completed",
    "blocked",
    "needs_approval",
    "failed",
    "interrupted",
    "worktree_locked",
    "invalid_task",
    "context_exhausted",
}
ACTIVE_JOB_STATUSES = {"pending", "running"}
MODEL_ORDER = (
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
)
MODEL_RANK = {model: rank for rank, model in enumerate(MODEL_ORDER)}
MODEL_POLICY_MODES = {"adaptive", "explicit_ceiling", "main_ceiling"}


class ManifestError(ValueError):
    """Raised when a run manifest or linked result violates schema v1."""


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
            raise ManifestError("mapping keys must be scalar values") from exc
        if duplicate:
            raise ManifestError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _mapping(
    value: Any,
    location: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    optional = optional or set()
    if not isinstance(value, dict):
        raise ManifestError(f"{location} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ManifestError(f"{location} keys must be strings")
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise ManifestError(f"unknown {location} key(s): {', '.join(unknown)}")
    missing = sorted(required - set(value))
    if missing:
        raise ManifestError(f"missing {location} key(s): {', '.join(missing)}")
    return value


def _nonempty(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{location} must be a nonempty string")
    return value


def _absolute_path(value: Any, location: str) -> Path:
    path = Path(_nonempty(value, location))
    if not path.is_absolute():
        raise ManifestError(f"{location} must be absolute")
    return path


def _validate_model_policy(value: Any, location: str) -> dict[str, Any]:
    policy = _mapping(value, location, {"mode", "maximum_model"})
    mode = policy["mode"]
    if mode not in MODEL_POLICY_MODES:
        raise ManifestError(f"unsupported {location}.mode: {mode!r}")
    maximum_model = policy["maximum_model"]
    if mode == "adaptive":
        if maximum_model is not None:
            raise ManifestError(f"{location}.maximum_model must be null in adaptive mode")
    elif maximum_model not in MODEL_RANK:
        supported = ", ".join(MODEL_ORDER)
        raise ManifestError(
            f"{location}.maximum_model must be one of {supported} in {mode} mode"
        )
    return policy


def _model_policy(run: dict[str, Any]) -> dict[str, Any]:
    value = run.get("model_policy")
    if value is None:
        return {"mode": "adaptive", "maximum_model": None}
    return _validate_model_policy(value, "run.model_policy")


def _requirements(run: dict[str, Any]) -> dict[str, Any]:
    value = run.get("requirements")
    if value is None:
        return {"revision": 1, "amendments": []}
    state = _mapping(value, "run.requirements", {"revision", "amendments"})
    amendments = state["amendments"]
    if not isinstance(amendments, list):
        raise ManifestError("run.requirements.amendments must be a list")
    if type(state["revision"]) is not int or state["revision"] != len(amendments) + 1:
        raise ManifestError("run.requirements.revision must equal amendment count + 1")
    fields = {"requirement_id", "before", "after", "source", "reason"}
    for index, raw_amendment in enumerate(amendments):
        location = f"run.requirements.amendments[{index}]"
        amendment = _mapping(raw_amendment, location, fields | {"revision"})
        if type(amendment["revision"]) is not int or amendment["revision"] != index + 2:
            raise ManifestError(f"{location}.revision must be {index + 2}")
        for field in fields:
            _nonempty(amendment[field], f"{location}.{field}")
    return state


def _select_model(
    requested_model: str, policy: dict[str, Any]
) -> tuple[str, str | None]:
    requested_model = _nonempty(requested_model, "requested model")
    mode = policy["mode"]
    if mode == "adaptive":
        return requested_model, None
    if requested_model not in MODEL_RANK:
        supported = ", ".join(MODEL_ORDER)
        raise ManifestError(
            f"cannot apply {mode} to unsupported requested model {requested_model!r}; "
            f"supported models: {supported}"
        )
    maximum_model = policy["maximum_model"]
    if MODEL_RANK[requested_model] > MODEL_RANK[maximum_model]:
        return maximum_model, mode
    return requested_model, None


def _load_yaml(path: Path, location: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read {location} {path}: {exc}") from exc
    try:
        value = yaml.load(text, Loader=UniqueKeyLoader)
    except ManifestError:
        raise
    except yaml.YAMLError as exc:
        raise ManifestError(f"invalid YAML in {location} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{location} {path} must contain a mapping")
    return value


def resolve_main_model(
    thread_id: str | None = None, codex_home: Path | None = None
) -> str:
    resolved_thread_id = _nonempty(
        thread_id or os.environ.get("CODEX_THREAD_ID"), "CODEX_THREAD_ID"
    )
    if codex_home is None:
        configured_home = os.environ.get("CODEX_HOME")
        codex_home = (
            Path(configured_home).expanduser()
            if configured_home
            else Path.home() / ".codex"
        )
    sessions_dir = codex_home / "sessions"
    candidates = sorted(
        path
        for path in sessions_dir.rglob("*.jsonl")
        if resolved_thread_id in path.name
    )
    if not candidates:
        raise ManifestError(
            f"cannot find rollout for CODEX_THREAD_ID {resolved_thread_id!r} "
            f"under {sessions_dir}"
        )
    if len(candidates) != 1:
        raise ManifestError(
            f"found multiple rollouts for CODEX_THREAD_ID {resolved_thread_id!r}"
        )

    model: str | None = None
    try:
        with candidates[0].open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                candidate: Any = None
                if item.get("type") == "turn_context":
                    candidate = payload.get("model")
                elif (
                    item.get("type") == "event_msg"
                    and payload.get("type") == "thread_settings_applied"
                ):
                    settings = payload.get("thread_settings")
                    if isinstance(settings, dict):
                        candidate = settings.get("model")
                elif item.get("type") == "world_state":
                    state = payload.get("state")
                    if isinstance(state, dict):
                        candidate = state.get("model")
                if isinstance(candidate, str) and candidate.strip():
                    model = candidate
    except OSError as exc:
        raise ManifestError(f"cannot read rollout {candidates[0]}: {exc}") from exc
    if model is None:
        raise ManifestError(f"rollout {candidates[0]} does not record the current model")
    return model


def _validate_manifest(value: dict[str, Any], path: Path) -> dict[str, Any]:
    root = _mapping(value, "run manifest", {"kind", "schema_version", "run", "jobs"})
    if root["kind"] != "develop-task-run":
        raise ManifestError("run manifest kind must be 'develop-task-run'")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise ManifestError("run manifest schema_version must be integer 1")

    run = _mapping(
        root["run"],
        "run",
        {"id", "backend", "workspace", "status", "started_at", "finished_at"},
        {"model_policy", "requirements"},
    )
    _nonempty(run["id"], "run.id")
    if run["backend"] != "runner":
        raise ManifestError("run.backend must be 'runner'")
    _absolute_path(run["workspace"], "run.workspace")
    if run["status"] not in RUN_STATUSES:
        raise ManifestError(f"unsupported run.status: {run['status']!r}")
    _nonempty(run["started_at"], "run.started_at")
    if run["finished_at"] is not None and not isinstance(run["finished_at"], str):
        raise ManifestError("run.finished_at must be a string or null")
    policy = _model_policy(run)
    requirements = _requirements(run)

    jobs = root["jobs"]
    if not isinstance(jobs, list):
        raise ManifestError("jobs must be a list")
    seen: set[str] = set()
    required = {
        "id",
        "role",
        "contract_revision",
        "approved_by_preflight",
        "task_path",
        "result_path",
        "status",
        "model",
        "reasoning_effort",
    }
    optional = {
        "execution_id",
        "usage",
        "requested_model",
        "selected_model",
        "limited_by",
        "requirements_revision",
    }
    for index, raw_job in enumerate(jobs):
        job = _mapping(raw_job, f"jobs[{index}]", required, optional)
        job_id = _nonempty(job["id"], f"jobs[{index}].id")
        if job_id in seen:
            raise ManifestError(f"duplicate job id: {job_id}")
        seen.add(job_id)
        _nonempty(job["role"], f"jobs[{index}].role")
        revision = job["contract_revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
            raise ManifestError(f"jobs[{index}].contract_revision must be a positive integer")
        if "requirements_revision" in job:
            requirements_revision = job["requirements_revision"]
            if (
                type(requirements_revision) is not int
                or not 1 <= requirements_revision <= requirements["revision"]
            ):
                raise ManifestError(
                    f"jobs[{index}].requirements_revision must name a recorded revision"
                )
        approval = job["approved_by_preflight"]
        if approval is not None and not isinstance(approval, str):
            raise ManifestError(f"jobs[{index}].approved_by_preflight must be a string or null")
        _absolute_path(job["task_path"], f"jobs[{index}].task_path")
        if job["result_path"] is not None:
            _absolute_path(job["result_path"], f"jobs[{index}].result_path")
        _nonempty(job["status"], f"jobs[{index}].status")
        model = _nonempty(job["model"], f"jobs[{index}].model")
        _nonempty(job["reasoning_effort"], f"jobs[{index}].reasoning_effort")
        selection_fields = {"requested_model", "selected_model", "limited_by"}
        present_selection_fields = selection_fields & set(job)
        if present_selection_fields and present_selection_fields != selection_fields:
            missing = sorted(selection_fields - present_selection_fields)
            raise ManifestError(
                f"jobs[{index}] model selection is missing: {', '.join(missing)}"
            )
        if present_selection_fields:
            requested_model = _nonempty(
                job["requested_model"], f"jobs[{index}].requested_model"
            )
            selected_model = _nonempty(
                job["selected_model"], f"jobs[{index}].selected_model"
            )
            expected_model, expected_limit = _select_model(requested_model, policy)
            if selected_model != expected_model:
                raise ManifestError(
                    f"jobs[{index}].selected_model does not match run.model_policy"
                )
            if job["limited_by"] != expected_limit:
                raise ManifestError(
                    f"jobs[{index}].limited_by does not match run.model_policy"
                )
            if model != selected_model:
                raise ManifestError(
                    f"jobs[{index}].model must equal jobs[{index}].selected_model"
                )
        else:
            selected_model, _ = _select_model(model, policy)
            if selected_model != model:
                raise ManifestError(f"jobs[{index}].model exceeds run.model_policy")
        if "execution_id" in job and job["execution_id"] is not None:
            _nonempty(job["execution_id"], f"jobs[{index}].execution_id")
        if "usage" in job and job["usage"] is not None and not isinstance(job["usage"], dict):
            raise ManifestError(f"jobs[{index}].usage must be a mapping or null")

    _ = path
    return root


def _validate_result(
    result: dict[str, Any], result_path: Path, task_path: Path, task_sha256: str, job_id: str
) -> tuple[str, str, dict[str, Any]]:
    root = _mapping(
        result,
        f"result {result_path}",
        {
            "kind",
            "schema_version",
            "execution",
            "task",
            "runner",
            "effective_configuration",
            "attempts",
            "usage",
            "outcome",
            "approval",
            "error",
        },
    )
    if root["kind"] != "agent-result" or root["schema_version"] != 1:
        raise ManifestError(f"result {result_path} is not agent-result schema v1")
    execution = root["execution"]
    task = root["task"]
    if not isinstance(execution, dict) or not isinstance(task, dict):
        raise ManifestError(f"result {result_path} has invalid execution or task metadata")
    execution_id = _nonempty(execution.get("id"), f"result {result_path} execution.id")
    status = execution.get("status")
    if status not in RESULT_STATUSES:
        raise ManifestError(f"result {result_path} has unsupported status {status!r}")
    recorded_task = _absolute_path(task.get("path"), f"result {result_path} task.path")
    if recorded_task.resolve() != task_path.resolve():
        raise ManifestError(f"result {result_path} points to a different task")
    if task.get("sha256") != task_sha256:
        raise ManifestError(f"result {result_path} task hash does not match immutable task.yaml")
    recorded_job_id = task.get("job_id")
    if status != "invalid_task" and recorded_job_id != job_id:
        raise ManifestError(f"result {result_path} job id does not match {job_id}")
    if status == "invalid_task" and recorded_job_id not in {None, job_id}:
        raise ManifestError(f"invalid-task result {result_path} belongs to another job")
    usage = root["usage"]
    if not isinstance(usage, dict):
        raise ManifestError(f"result {result_path} usage must be a mapping")
    return status, execution_id, usage


def _reconcile_document(document: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    manifest = _validate_manifest(document, manifest_path)
    for raw_job in manifest["jobs"]:
        job = raw_job
        task_path = Path(job["task_path"])
        try:
            task_bytes = task_path.read_bytes()
        except OSError as exc:
            raise ManifestError(f"cannot read immutable task {task_path}: {exc}") from exc
        result_dir = task_path.parent / "results"
        result_paths = sorted(path.resolve() for path in result_dir.glob("*.yaml"))
        if len(result_paths) > 1:
            raise ManifestError(
                f"job {job['id']} has {len(result_paths)} executions; "
                "create a new job directory per invocation"
            )
        if not result_paths:
            job.update(
                {
                    "result_path": None,
                    "status": "pending",
                    "execution_id": None,
                    "usage": None,
                }
            )
            continue
        result_path = result_paths[0]
        result = _load_yaml(result_path, "result")
        status, execution_id, usage = _validate_result(
            result,
            result_path,
            task_path,
            hashlib.sha256(task_bytes).hexdigest(),
            job["id"],
        )
        job.update(
            {
                "result_path": str(result_path),
                "status": status,
                "execution_id": execution_id,
                "usage": usage,
            }
        )
    return manifest


def _unregistered_task_paths(manifest: dict[str, Any], manifest_path: Path) -> list[Path]:
    registered = {Path(job["task_path"]).resolve() for job in manifest["jobs"]}
    jobs_dir = manifest_path.parent / "jobs"
    return sorted(
        task_path.resolve()
        for task_path in jobs_dir.glob("*/task.yaml")
        if task_path.resolve() not in registered
    )


def _validate_task_source(task_source_argument: str) -> tuple[bytes, dict[str, Any]]:
    source_path = Path(os.path.abspath(os.path.expanduser(task_source_argument)))
    try:
        task_bytes = source_path.read_bytes()
    except OSError as exc:
        raise ManifestError(f"cannot read task source {source_path}: {exc}") from exc

    from agent_runner import TaskValidationError, parse_task

    try:
        task = parse_task(task_bytes, source_path)
    except TaskValidationError as exc:
        raise ManifestError(f"invalid task source {source_path}: {exc}") from exc
    return task_bytes, task


def _create_immutable_task(job_dir: Path, task_bytes: bytes) -> Path:
    jobs_dir = job_dir.parent
    jobs_dir.mkdir(parents=True, exist_ok=True)
    if job_dir.exists():
        raise ManifestError(f"job directory already exists: {job_dir}")

    temporary_dir: Path | None = Path(
        tempfile.mkdtemp(prefix=f".{job_dir.name}.", dir=jobs_dir)
    )
    try:
        assert temporary_dir is not None
        temporary_task = temporary_dir / "task.yaml"
        with temporary_task.open("wb") as handle:
            handle.write(task_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_dir, job_dir)
        temporary_dir = None
        directory_fd = os.open(jobs_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_dir is not None:
            with contextlib.suppress(FileNotFoundError):
                (temporary_dir / "task.yaml").unlink()
            with contextlib.suppress(OSError):
                temporary_dir.rmdir()
    return job_dir / "task.yaml"


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


@contextmanager
def _locked_manifest(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_absolute():
        raise ManifestError("run manifest path must be absolute")
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        document = _load_yaml(path, "run manifest")
        yield document
        _atomic_write(path, document)


def reconcile_manifest(path_argument: str) -> Path:
    path = Path(os.path.abspath(os.path.expanduser(path_argument)))
    with _locked_manifest(path) as document:
        _reconcile_document(document, path)
    return path


def new_job_manifest(
    path_argument: str,
    task_source_argument: str,
    role: str,
    contract_revision: int,
    approved_by_preflight: str | None,
) -> Path:
    path = Path(os.path.abspath(os.path.expanduser(path_argument)))
    task_bytes, task = _validate_task_source(task_source_argument)
    role = _nonempty(role, "role")
    if (
        isinstance(contract_revision, bool)
        or not isinstance(contract_revision, int)
        or contract_revision <= 0
    ):
        raise ManifestError("contract revision must be a positive integer")
    if approved_by_preflight is not None:
        approved_by_preflight = _nonempty(
            approved_by_preflight, "approved_by_preflight"
        )

    job_id = task["job"]["id"]
    if job_id in {".", ".."} or Path(job_id).name != job_id:
        raise ManifestError("task job.id must be a safe job directory name")

    with _locked_manifest(path) as document:
        manifest = _reconcile_document(document, path)
        if manifest["run"]["status"] != "running":
            raise ManifestError("cannot add a job to a terminal run; resume it first")
        unregistered = _unregistered_task_paths(manifest, path)
        if unregistered:
            raise ManifestError(
                "cannot add a job while unregistered task files exist: "
                + ", ".join(str(item) for item in unregistered)
            )
        if any(job["id"] == job_id for job in manifest["jobs"]):
            raise ManifestError(f"duplicate job id: {job_id}")

        workspace = Path(task["workspace"]["cwd"]).resolve()
        run_workspace = Path(manifest["run"]["workspace"]).resolve()
        if workspace != run_workspace:
            raise ManifestError(
                f"task workspace {workspace} does not match run workspace {run_workspace}"
            )

        requested_model = task["agent"]["model"]
        selected_model, limited_by = _select_model(
            requested_model, _model_policy(manifest["run"])
        )
        if selected_model != requested_model:
            task["agent"]["model"] = selected_model
            task_bytes = yaml.safe_dump(
                task, allow_unicode=True, sort_keys=False
            ).encode("utf-8")

        task_path = _create_immutable_task(path.parent / "jobs" / job_id, task_bytes)
        manifest["jobs"].append(
            {
                "id": job_id,
                "role": role,
                "contract_revision": contract_revision,
                "requirements_revision": _requirements(manifest["run"])["revision"],
                "approved_by_preflight": approved_by_preflight,
                "task_path": str(task_path.resolve()),
                "result_path": None,
                "status": "pending",
                "execution_id": None,
                "usage": None,
                "model": selected_model,
                "requested_model": requested_model,
                "selected_model": selected_model,
                "limited_by": limited_by,
                "reasoning_effort": task["agent"]["reasoning_effort"],
            }
        )
    return task_path.resolve()


def amend_requirement_manifest(
    path_argument: str,
    requirement_id: str,
    before: str,
    after: str,
    source: str,
    reason: str,
) -> Path:
    amendment: dict[str, Any] = {
        "requirement_id": _nonempty(requirement_id, "requirement_id"),
        "before": _nonempty(before, "before"),
        "after": _nonempty(after, "after"),
        "source": _nonempty(source, "source"),
        "reason": _nonempty(reason, "reason"),
    }
    path = Path(os.path.abspath(os.path.expanduser(path_argument)))
    with _locked_manifest(path) as document:
        manifest = _reconcile_document(document, path)
        if manifest["run"]["status"] != "running":
            raise ManifestError("cannot amend requirements of a terminal run; resume it first")
        state = _requirements(manifest["run"])
        state["revision"] += 1
        amendment["revision"] = state["revision"]
        state["amendments"].append(amendment)
        manifest["run"]["requirements"] = state
    return path


def finish_manifest(path_argument: str, status: str) -> Path:
    if status not in FINAL_RUN_STATUSES:
        raise ManifestError(f"unsupported final run status: {status}")
    path = Path(os.path.abspath(os.path.expanduser(path_argument)))
    with _locked_manifest(path) as document:
        manifest = _reconcile_document(document, path)
        unregistered = _unregistered_task_paths(manifest, path)
        if unregistered:
            raise ManifestError(
                "cannot finish run with unregistered task files: "
                + ", ".join(str(item) for item in unregistered)
            )
        active = [job["id"] for job in manifest["jobs"] if job["status"] in ACTIVE_JOB_STATUSES]
        if active:
            raise ManifestError(f"cannot finish run with active jobs: {', '.join(active)}")
        manifest["run"]["status"] = status
        manifest["run"]["finished_at"] = _utc_now()
    return path


def resume_manifest(path_argument: str) -> Path:
    path = Path(os.path.abspath(os.path.expanduser(path_argument)))
    with _locked_manifest(path) as document:
        manifest = _reconcile_document(document, path)
        manifest["run"]["status"] = "running"
        manifest["run"]["finished_at"] = None
    return path


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-run-manifest",
        description=(
            "Resolve the main model or atomically register, amend, reconcile, and finalize "
            "one develop-task run.yaml."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "current-model", help="print the model recorded for the current Codex thread"
    )
    new_job = commands.add_parser(
        "new-job", help="validate a task, create its job directory, and register it"
    )
    new_job.add_argument("run_manifest", help="absolute path to run.yaml")
    new_job.add_argument("task_source", help="path to the prepared agent-task v2 YAML")
    new_job.add_argument("--role", required=True, help="job role recorded in run.yaml")
    new_job.add_argument("--contract-revision", required=True, type=int)
    new_job.add_argument("--approved-by-preflight")
    amendment = commands.add_parser(
        "amend-requirement", help="record one explicitly approved developer amendment"
    )
    amendment.add_argument("run_manifest", help="absolute path to run.yaml")
    amendment.add_argument("requirement_id", help="stable ID from the source requirements")
    for field in ("before", "after", "source", "reason"):
        amendment.add_argument(f"--{field}", required=True)
    reconcile = commands.add_parser("reconcile", help="rebuild job execution fields")
    reconcile.add_argument("run_manifest", help="absolute path to run.yaml")
    finish = commands.add_parser("finish", help="reconcile and set a terminal run status")
    finish.add_argument("run_manifest", help="absolute path to run.yaml")
    finish.add_argument("status", choices=sorted(FINAL_RUN_STATUSES))
    resume = commands.add_parser("resume", help="reconcile and reopen a terminal run")
    resume.add_argument("run_manifest", help="absolute path to run.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        if args.command == "current-model":
            output = resolve_main_model()
        elif args.command == "new-job":
            path = new_job_manifest(
                args.run_manifest,
                args.task_source,
                args.role,
                args.contract_revision,
                args.approved_by_preflight,
            )
            output = str(path.resolve())
        elif args.command == "reconcile":
            path = reconcile_manifest(args.run_manifest)
            output = str(path.resolve())
        elif args.command == "amend-requirement":
            path = amend_requirement_manifest(
                args.run_manifest,
                args.requirement_id,
                args.before,
                args.after,
                args.source,
                args.reason,
            )
            output = str(path.resolve())
        elif args.command == "finish":
            path = finish_manifest(args.run_manifest, args.status)
            output = str(path.resolve())
        else:
            path = resume_manifest(args.run_manifest)
            output = str(path.resolve())
    except (ManifestError, OSError) as exc:
        print(f"agent-run-manifest: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
