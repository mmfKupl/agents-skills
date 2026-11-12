"""Route, build, register, run, and reconcile one develop-task job, and report usage."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import run_manifest as manifest

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

PROFILES = ("fast", "standard", "deep", "critical", "exceptional")
ROLES = (
    "preflight-review",
    "implementation-worker",
    "postflight-review",
    "repo-practice-review",
    "best-practice-review",
    "test-review",
    "code-simplicity-review",
    "diagnosis-review",
)
SLUGS = {
    "preflight-review": "preflight",
    "implementation-worker": "implementation",
    "postflight-review": "postflight",
    "repo-practice-review": "repo-practice",
    "best-practice-review": "best-practice",
    "test-review": "test-review",
    "code-simplicity-review": "simplicity",
    "diagnosis-review": "diagnosis",
}
# The default matrix in GPT names; the other vendor maps through its peer.
PREFLIGHT = {
    "fast": ("gpt-6.1-sol", "medium"),
    "standard": ("gpt-6.1-sol", "medium"),
    "deep": ("gpt-6.1-sol", "high"),
    "critical": ("gpt-6.1-sol", "xhigh"),
    "exceptional": ("gpt-6-astra", "high"),
}
POSTFLIGHT = {
    "fast": ("gpt-6.1-sol", "low"),
    "standard": ("gpt-6.1-sol", "medium"),
    "deep": ("gpt-6.1-sol", "high"),
    "critical": ("gpt-6.1-sol", "xhigh"),
    "exceptional": ("gpt-6-astra", "high"),
}
WRITER = {
    "fast": ("gpt-6.1-terra", "medium"),
    "standard": ("gpt-6.1-terra", "high"),
    "deep": ("gpt-6.1-sol", "high"),
    "critical": ("gpt-6.1-sol", "high"),
    "exceptional": ("gpt-6.1-sol", "high"),
}
SLICES = {
    "visual": ("gpt-6.1-terra", "high", ("deep", "critical", "exceptional")),
    "prose": ("gpt-6.1-terra", "high", ("deep", "critical", "exceptional")),
    "critical-combined": ("gpt-6.1-sol", "xhigh", ("critical",)),
    "exceptional": ("gpt-6-astra", "high", ("exceptional",)),
}
BUDGETS = {
    "fast": (155000, 180000, 20, 2),
    "standard": (155000, 180000, 30, 3),
    "deep": (210000, 240000, 45, 4),
    "critical": (350000, 400000, 60, 5),
    "exceptional": (220000, 250000, 60, 5),
}
GPT_PEER = {gpt: claude for claude, gpt in manifest.CLAUDE_MODEL_PEERS.items()}
GPT_PEER["gpt-6-sol"] = "claude-opus-5-5"
# On Claude, Fable high replaces Opus xhigh: it scores higher at about the same cost per
# task. Its safeguards refuse much security work, so a routed Fable job that a safety
# refusal stops reruns on the strongest Opus route.
CLAUDE_UPGRADES = {("gpt-6.1-sol", "xhigh"): ("claude-fable-5-2", "high")}
REFUSAL_ROUTE = ("gpt-6.1-sol", "xhigh")
REFUSAL_RETRY = """\
A previous job for this packet ran on Claude Fable and stopped on a safety refusal.
This is the rerun on Claude Opus. The worktree may hold that job's partial edits:
check `git status` before you start.

"""
ADAPTER = """\
The runner requires one universal structured output object. Perform the role
contract exactly, but place its complete required role response inside the
universal `report` string. Use `summary` for a short semantic summary and the
remaining universal fields for evidence, validation, warnings, and questions.
The universal status describes job execution, not the role decision:
- use `completed` when the role produced its decision/report, including
  preflight revise/blocked decisions and postflight Approval: no;
- use `blocked` only when the role itself could not execute;
- use `checkpoint` only when instructed by the runner for context rotation.
Do not create subagents or delegate.
"""
WORKER_ADAPTER = """\
Encode role status `implemented` as universal `completed`. Encode role status
`replan_required` or `blocked` as universal `blocked`, and keep the exact role
status and explanation in `report`.
"""


SPECIALISTS = ("repo-practice-review", "best-practice-review", "test-review", "code-simplicity-review")
DIAGNOSIS = {
    "fast": ("gpt-6.1-sol", "high"),
    "standard": ("gpt-6.1-sol", "high"),
    "deep": ("gpt-6.1-sol", "high"),
    "critical": ("gpt-6.1-sol", "xhigh"),
    "exceptional": ("gpt-6-astra", "high"),
}


def route(
    role: str, profile: str, *, slice_kind: str | None = None, gate: str = "preflight",
    lookup: str | None = None,
) -> tuple[str, str, str]:
    """Return the GPT-named model, effort, and the rule that chose them.

    For diagnosis-review, `profile` is the profile of the unresolved cause.
    """
    if role not in ROLES:
        raise manifest.ManifestError(f"unsupported role: {role!r}")
    if profile not in PROFILES:
        raise manifest.ManifestError(f"unsupported profile: {profile!r}")
    if gate != "preflight" and role not in SPECIALISTS:
        raise manifest.ManifestError(f"--for applies only to specialists, not {role}")
    if lookup is not None:
        if role not in SPECIALISTS:
            raise manifest.ManifestError(f"--lookup applies only to specialists, not {role}")
        if lookup not in ("low", "medium", "high"):
            raise manifest.ManifestError(f"unsupported lookup effort: {lookup!r}")
        return "gpt-6-luna", lookup, "bounded factual lookup"
    if slice_kind is not None:
        if slice_kind not in SLICES:
            raise manifest.ManifestError(f"unsupported slice: {slice_kind!r}")
        if role != "implementation-worker":
            raise manifest.ManifestError(f"--slice {slice_kind} does not apply to {role}")
        model, effort, profiles = SLICES[slice_kind]
        if profile not in profiles:
            raise manifest.ManifestError(
                f"--slice {slice_kind} applies only to profiles: {', '.join(profiles)}"
            )
        return model, effort, f"{slice_kind} slice in a {profile} task"
    if role == "preflight-review":
        return (*PREFLIGHT[profile], f"{profile} preflight")
    if role == "postflight-review":
        return (*POSTFLIGHT[profile], f"{profile} postflight")
    if role == "implementation-worker":
        return (*WRITER[profile], f"{profile} writer")
    if role == "diagnosis-review":
        return (*DIAGNOSIS[profile], f"diagnosis of a {profile} cause")
    table = {"postflight": POSTFLIGHT, "diagnosis": DIAGNOSIS}.get(gate, PREFLIGHT)
    return (*table[profile], f"specialist for the {profile} {gate} gate")


def home_vendor() -> str:
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    return "claude" if os.environ.get("CLAUDECODE") == "1" else "codex"


def target_vendor(role: str, gate: str, vendor: str) -> str:
    """Run every job on the host vendor unless the user named a vendor or cross review."""
    home = home_vendor()
    if vendor in ("codex", "claude"):
        return vendor
    cross = role in ("postflight-review", "diagnosis-review") or gate in (
        "postflight", "diagnosis"
    )
    if vendor == "cross" and cross:
        return "codex" if home == "claude" else "claude"
    return home


def vendor_model(model: str, vendor: str) -> str:
    if vendor == "claude":
        return GPT_PEER.get(model, model)
    return manifest.CLAUDE_MODEL_PEERS.get(model, model)


def ceiling_policy(ceiling: str | None) -> dict[str, Any]:
    if not ceiling:
        return {"mode": "adaptive", "maximum_model": None}
    return {"mode": "explicit_ceiling", "maximum_model": manifest._model_id(ceiling)}


def claude_upgrade(model: str, effort: str, vendor: str, policy: dict[str, Any]) -> tuple[str, str] | None:
    """Return the Claude route that replaces a matrix route, unless the ceiling is below it."""
    upgrade = CLAUDE_UPGRADES.get((model, effort)) if vendor == "claude" else None
    if upgrade is None or manifest._select_model(upgrade[0], policy)[1] is not None:
        return None
    return upgrade


def resolve(
    model: str, effort: str, rule: str, vendor: str, policy: dict[str, Any]
) -> tuple[str, str, str]:
    """Return the vendor's model, effort, and rule for a matrix route."""
    upgrade = claude_upgrade(model, effort, vendor, policy)
    if upgrade:
        return *upgrade, f"{rule}; Fable in place of Opus {effort}"
    return vendor_model(model, vendor), effort, rule


def role_instructions(role: str) -> str:
    if tomllib is None:
        raise manifest.ManifestError("reading role files needs Python 3.11 or newer")
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    path = home / "agents" / f"{role}.toml"
    try:
        contract = tomllib.loads(path.read_text(encoding="utf-8"))["developer_instructions"]
    except (OSError, KeyError, ValueError) as exc:
        raise manifest.ManifestError(f"cannot read role contract {path}: {exc}") from exc
    extra = WORKER_ADAPTER if role == "implementation-worker" else ""
    return f"{contract.rstrip()}\n\n{ADAPTER}{extra}"


def build_task(
    *, job_id: str, role: str, profile: str, model: str, effort: str, prompt: str,
    workspace: str, unrestricted: bool,
) -> dict[str, Any]:
    if role == "implementation-worker":
        sandbox = "danger_full_access" if unrestricted else "workspace_write"
    elif unrestricted:
        raise manifest.ManifestError("--unrestricted applies only to implementation-worker")
    else:
        sandbox = "read_only"
    soft, hard, grace, attempts = BUDGETS[profile]
    return {
        "kind": "agent-task",
        "schema_version": 2,
        "job": {"id": job_id, "prompt": prompt},
        "workspace": {"cwd": workspace},
        "agent": {
            "model": model,
            "reasoning_effort": effort,
            "developer_instructions": role_instructions(role),
        },
        "permissions": {
            "sandbox_mode": sandbox,
            "approval_policy": "never",
            "network_access": sandbox == "danger_full_access",
        },
        "supervision": {
            "context": {
                "soft_limit_tokens": soft,
                "hard_limit_tokens": hard,
                "checkpoint_grace_seconds": grace,
            },
            "max_attempts": attempts,
        },
    }


def _next_job_id(jobs: list[dict[str, Any]], role: str) -> str:
    taken = {job["id"] for job in jobs}
    number = len(jobs) + 1
    while True:
        job_id = f"{number:03d}-{SLUGS[role]}"
        if job_id not in taken:
            return job_id
        number += 1


def _runner_path(explicit: str | None) -> str:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    for candidate in (
        explicit,
        os.environ.get("CODEX_AGENT_RUNNER"),
        str(Path(sys.argv[0]).resolve().parent / "agent-runner"),
        str(home / "tools" / "agent-runner" / "bin" / "agent-runner"),
        shutil.which("agent-runner"),
    ):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise manifest.ManifestError("cannot find an executable agent-runner")


def capped(model: str, ceiling: str | None) -> str:
    if not ceiling:
        return model
    return manifest._select_model(model, ceiling_policy(ceiling))[0]


def dispatch(
    *, role: str, profile: str, prompt_file: str, run_manifest: str | None = None,
    workspace: str | None = None, ceiling: str | None = None,
    contract_revision: int | None = None, approved_by_preflight: str | None = None,
    slice_kind: str | None = None, gate: str = "preflight", lookup: str | None = None,
    vendor: str = "auto", model: str | None = None, effort: str | None = None,
    reason: str | None = None, job_id: str | None = None, unrestricted: bool = False,
    runner: str | None = None,
) -> tuple[int, str]:
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    if (model or effort) and not (model and effort and reason):
        raise manifest.ManifestError("--model and --effort need each other and a --reason")
    if model:
        chosen_model, chosen_effort, rule = model, effort, f"override: {reason}"
    else:
        chosen_model, chosen_effort, rule = route(
            role, profile, slice_kind=slice_kind, gate=gate, lookup=lookup
        )
    target = target_vendor(role, gate, vendor)
    runner_path = _runner_path(runner)

    def plan(policy: dict[str, Any]) -> tuple[str, str, str]:
        if model:
            return vendor_model(chosen_model, target), chosen_effort, rule
        return resolve(chosen_model, chosen_effort, rule, target, policy)

    def header(selected: str) -> str:
        return (
            f"Routing: {profile} profile, {role}, {selected} {job_effort} "
            f"({job_rule}; {target} vendor).\n\n"
        )

    if run_manifest is not None:
        if ceiling:
            raise manifest.ManifestError("--ceiling is for --no-manifest; the run has its own policy")
        if contract_revision is None:
            raise manifest.ManifestError("--contract-revision is required with a run manifest")
        if role in ("implementation-worker", "postflight-review") and not approved_by_preflight:
            raise manifest.ManifestError(f"{role} needs --approved-by-preflight")
        run_path = Path(os.path.abspath(run_manifest))
        fixed_id = job_id
        for _ in range(5):
            document = manifest._load_yaml(run_path, "run manifest")
            job_id = fixed_id or _next_job_id(document.get("jobs") or [], role)
            policy = manifest._model_policy(document["run"])
            requested, job_effort, job_rule = plan(policy)
            selected = manifest._select_model(requested, policy)[0]
            with tempfile.TemporaryDirectory() as draft_dir:
                draft = Path(draft_dir) / "task.yaml"
                task = build_task(
                    job_id=job_id, role=role, profile=profile, model=requested,
                    effort=job_effort, prompt=header(selected) + prompt,
                    workspace=document["run"]["workspace"], unrestricted=unrestricted,
                )
                draft.write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), "utf-8")
                try:
                    task_path = manifest.new_job_manifest(
                        str(run_path), str(draft), role, contract_revision, approved_by_preflight
                    )
                    break
                except manifest.ManifestError as exc:
                    # A parallel dispatch took this sequence number.
                    if fixed_id or "duplicate job id" not in str(exc):
                        raise
        else:
            raise manifest.ManifestError("could not allocate a job id")
    else:
        if not workspace:
            raise manifest.ManifestError("--workspace is required without a run manifest")
        job_id = job_id or SLUGS[role]
        requested, job_effort, job_rule = plan(ceiling_policy(ceiling))
        selected = capped(requested, ceiling)
        job_dir = Path(tempfile.mkdtemp(prefix="agent-job-")) / job_id
        job_dir.mkdir(mode=0o700)
        task = build_task(
            job_id=job_id, role=role, profile=profile, model=selected,
            effort=job_effort, prompt=header(selected) + prompt,
            workspace=str(Path(workspace).resolve()), unrestricted=unrestricted,
        )
        task_path = job_dir / "task.yaml"
        task_path.write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), "utf-8")

    process = subprocess.run([runner_path, str(task_path)], stdout=subprocess.PIPE, text=True)
    summary: dict[str, Any] = {
        "job": job_id, "role": role, "route": job_rule, "vendor": target,
        "requested_model": requested, "effort": job_effort, "task": str(task_path),
        "runner_exit": process.returncode,
    }
    code = process.returncode
    if run_manifest is not None:
        try:
            manifest.reconcile_manifest(str(run_path))
        except manifest.ManifestError as exc:
            summary["reconcile_error"] = str(exc)
            code = code or 3
    lines = process.stdout.strip().splitlines()
    if process.returncode == 0 and lines:
        result_path = Path(lines[-1])
        result = manifest._load_yaml(result_path, "result")
        try:
            manifest._validate_result(
                result, result_path, Path(task_path),
                manifest.hashlib.sha256(Path(task_path).read_bytes()).hexdigest(), job_id,
            )
        except manifest.ManifestError as exc:
            summary["result_error"] = str(exc)
            code = code or 3
        outcome = result.get("outcome") or {}
        summary.update(
            model=(result.get("effective_configuration") or {}).get("agent", {}).get("model"),
            execution_status=result["execution"]["status"],
            outcome_status=outcome.get("status"),
            summary=outcome.get("summary"),
            result=str(result_path),
            events=str(result_path.with_suffix(".events.jsonl")),
            error=result.get("error"),
            report=outcome.get("report"),
        )
    refused = (summary.get("error") or {}).get("type") == "refusal"
    if refused and not model and str(summary.get("model")).startswith("claude-fable-"):
        with tempfile.TemporaryDirectory() as retry_dir:
            retry_prompt = Path(retry_dir) / "packet.md"
            retry_prompt.write_text(REFUSAL_RETRY + prompt, encoding="utf-8")
            code, output = dispatch(
                role=role, profile=profile, prompt_file=str(retry_prompt),
                run_manifest=run_manifest, workspace=workspace, ceiling=ceiling,
                contract_revision=contract_revision, approved_by_preflight=approved_by_preflight,
                slice_kind=slice_kind, gate=gate, lookup=lookup, vendor=vendor,
                model=REFUSAL_ROUTE[0], effort=REFUSAL_ROUTE[1],
                reason=f"{job_id} on {requested} was refused", unrestricted=unrestricted,
                runner=runner,
            )
        retry = yaml.safe_load(output)
        retry["refused"] = {"job": job_id, "model": requested, "error": summary["error"]["message"]}
        return code, yaml.safe_dump(retry, sort_keys=False, allow_unicode=True)
    return code, yaml.safe_dump(summary, sort_keys=False, allow_unicode=True)


def _claude_main_usage(session_id: str) -> dict[str, int] | None:
    transcript = manifest._claude_transcript(session_id)
    if transcript is None:
        return None
    last: dict[str, tuple[dict[str, Any], Any]] = {}
    for entry in manifest._claude_entries(transcript):
        message = entry.get("message") or {}
        if entry.get("type") == "assistant" and message.get("usage"):
            last[message.get("id") or entry.get("uuid")] = (message["usage"], message.get("stop_reason"))
    usage = dict.fromkeys(("uncached", "cached", "write", "output", "reasoning"), 0)
    usage["missing"] = 0
    usage["requests"] = len(last)
    for value, stop_reason in last.values():
        usage["uncached"] += value.get("input_tokens", 0)
        usage["cached"] += value.get("cache_read_input_tokens", 0)
        usage["write"] += value.get("cache_creation_input_tokens", 0)
        if stop_reason is None:
            usage["missing"] += 1
            continue
        usage["output"] += value.get("output_tokens", 0)
        usage["reasoning"] += (value.get("output_tokens_details") or {}).get("thinking_tokens", 0)
    return usage


def _codex_main_usage(thread_id: str) -> dict[str, int] | None:
    try:
        paths = manifest._rollout_paths(thread_id)
    except manifest.ManifestError:
        return None
    latest: tuple[str, dict[str, Any]] | None = None
    for path in paths:
        for item in manifest._rollout_items(path):
            payload = item.get("payload") or {}
            total = (payload.get("info") or {}).get("total_token_usage")
            if payload.get("type") == "token_count" and total:
                stamp = item.get("timestamp") or ""
                if latest is None or stamp >= latest[0]:
                    latest = (stamp, total)
    if latest is None:
        return None
    total = latest[1]
    return {
        "uncached": total.get("input_tokens", 0) - total.get("cached_input_tokens", 0),
        "cached": total.get("cached_input_tokens", 0),
        "write": total.get("cache_write_input_tokens", 0),
        "output": total.get("output_tokens", 0),
        "reasoning": total.get("reasoning_output_tokens", 0),
        "missing": 0, "requests": 0,
    }


def usage_table(run_manifest: str) -> str:
    path = Path(os.path.abspath(run_manifest))
    manifest.reconcile_manifest(str(path))
    document = manifest._load_yaml(path, "run manifest")
    rows = [
        "| Job | Model / effort | Status | Attempts | Uncached in | Cached in | Cache write | Out (reasoning) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    totals = dict.fromkeys(("uncached", "cached", "write", "output", "reasoning"), 0)
    missing = 0
    attempt_total = 0
    for job in document.get("jobs") or []:
        usage = job.get("usage")
        attempts = "n/a"
        if job.get("result_path"):
            with_attempts = manifest._load_yaml(Path(job["result_path"]), "result")
            attempts = str(len(with_attempts.get("attempts") or []))
            attempt_total += int(attempts)
        label = f"{job['model']} {job['reasoning_effort']}"
        if job.get("limited_by"):
            label += f" (capped from {job.get('requested_model')})"
        if not usage or not usage.get("input_tokens"):
            missing += 1
            rows.append(f"| {job['id']} | {label} | {job['status']} | {attempts} | n/a | n/a | n/a | n/a |")
            continue
        cached = usage.get("cached_input_tokens", 0)
        write = usage.get("cache_write_input_tokens", 0)
        values = {
            "uncached": usage.get("input_tokens", 0) - cached - write, "cached": cached,
            "write": write, "output": usage.get("output_tokens", 0),
            "reasoning": usage.get("reasoning_output_tokens", 0),
        }
        for key, value in values.items():
            totals[key] += value
        rows.append(
            f"| {job['id']} | {label} | {job['status']} | {attempts} | {values['uncached']:,} | "
            f"{values['cached']:,} | {values['write']:,} | {values['output']:,} ({values['reasoning']:,}) |"
        )
    jobs = len(document.get("jobs") or [])
    partial = f", partial: {missing} of {jobs} jobs without usage" if missing else ""
    rows.append(
        f"| Total: {jobs} jobs{partial} | | | {attempt_total} | {totals['uncached']:,} | {totals['cached']:,} | "
        f"{totals['write']:,} | {totals['output']:,} ({totals['reasoning']:,}) |"
    )
    main = None
    if os.environ.get("CODEX_THREAD_ID"):
        main = _codex_main_usage(os.environ["CODEX_THREAD_ID"])
    elif os.environ.get("CLAUDE_CODE_SESSION_ID"):
        main = _claude_main_usage(os.environ["CLAUDE_CODE_SESSION_ID"])
    if main is None:
        rows.append("| main | | | | n/a | n/a | n/a | n/a |")
    else:
        out = f"{main['output']:,} ({main['reasoning']:,})"
        if main["missing"] and main["missing"] == main["requests"]:
            out = "n/a"
        elif main["missing"]:
            out = f">= {out}, {main['missing']} of {main['requests']} requests unknown"
        rows.append(
            f"| main | | | | {main['uncached']:,} | {main['cached']:,} | {main['write']:,} | {out} |"
        )
    return "\n".join(rows)
