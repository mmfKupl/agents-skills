from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_dispatch
import run_manifest

FAKE_RUNNER = """#!{python}
import hashlib, os, sys, yaml
from pathlib import Path
task_path = Path(sys.argv[1])
task = yaml.safe_load(task_path.read_text())
results = task_path.parent / "results"
results.mkdir()
result = results / "exec-1.yaml"
value = {{
    "kind": "agent-result", "schema_version": 1,
    "execution": {{"id": "exec-1", "status": "completed"}},
    "task": {{"path": str(task_path), "sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
              "job_id": task["job"]["id"]}},
    "runner": {{}}, "effective_configuration": {{"agent": {{"model": task["agent"]["model"]}}}},
    "attempts": [{{"number": 1}}],
    "usage": {{"input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": 10,
               "output_tokens": 7, "reasoning_output_tokens": 2, "total_tokens": 107}},
    "outcome": {{"status": "completed", "summary": "done", "report": "Decision: proceed"}},
    "approval": {{}}, "error": None,
}}
if os.environ.get("FAKE_REFUSE") and task["agent"]["model"].startswith("claude-fable-"):
    value.update(
        execution={{"id": "exec-1", "status": "failed"}}, outcome=None,
        error={{"type": "refusal", "message": "a safety refusal stopped the Claude run"}},
    )
result.write_text(yaml.safe_dump(value))
print(result)
"""


class RouteTests(unittest.TestCase):
    def test_matrix(self) -> None:
        cases = {
            ("preflight-review", "standard"): ("gpt-6.1-sol", "medium"),
            ("implementation-worker", "fast"): ("gpt-6.1-terra", "medium"),
            ("implementation-worker", "standard"): ("gpt-6.1-terra", "high"),
            ("implementation-worker", "deep"): ("gpt-6.1-sol", "high"),
            ("postflight-review", "fast"): ("gpt-6.1-sol", "low"),
            ("postflight-review", "critical"): ("gpt-6.1-sol", "xhigh"),
            ("preflight-review", "exceptional"): ("gpt-6-astra", "high"),
            ("diagnosis-review", "standard"): ("gpt-6.1-sol", "high"),
            ("diagnosis-review", "critical"): ("gpt-6.1-sol", "xhigh"),
            ("diagnosis-review", "fast"): ("gpt-6.1-sol", "high"),
        }
        for (role, profile), expected in cases.items():
            self.assertEqual(run_dispatch.route(role, profile)[:2], expected, (role, profile))

    def test_slices_lookup_and_gates(self) -> None:
        route = run_dispatch.route
        self.assertEqual(route("implementation-worker", "deep", slice_kind="visual")[:2],
                         ("gpt-6.1-terra", "high"))
        self.assertEqual(route("implementation-worker", "exceptional", slice_kind="exceptional")[:2],
                         ("gpt-6-astra", "high"))
        self.assertEqual(route("test-review", "standard", lookup="medium")[:2], ("gpt-6-luna", "medium"))
        self.assertEqual(route("test-review", "standard", lookup="high")[:2], ("gpt-6-luna", "high"))
        self.assertEqual(route("test-review", "standard", gate="diagnosis")[:2], ("gpt-6.1-sol", "high"))
        self.assertEqual(route("diagnosis-review", "exceptional")[:2], ("gpt-6-astra", "high"))
        self.assertEqual(route("diagnosis-review", "deep")[:2], ("gpt-6.1-sol", "high"))
        for bad in ({"lookup": "medium"}, {"gate": "postflight"}):
            with self.assertRaises(run_manifest.ManifestError):
                route("implementation-worker", "fast", **bad)
        self.assertEqual(route("code-simplicity-review", "fast", gate="postflight")[:2],
                         ("gpt-6.1-sol", "low"))
        for bad in ({"slice_kind": "visual"}, {"slice_kind": "critical-combined"}):
            with self.assertRaises(run_manifest.ManifestError):
                route("implementation-worker", "standard", **bad)
        with self.assertRaises(run_manifest.ManifestError):
            route("preflight-review", "deep", slice_kind="visual")

    def test_route_command(self) -> None:
        with patch.dict(os.environ, {"CLAUDECODE": "1", "CODEX_THREAD_ID": ""}), patch("builtins.print") as printed:
            code = run_manifest.main(["route", "--role", "postflight-review", "--profile", "standard",
                                      "--vendor", "cross"])
            self.assertEqual(code, 0)
            self.assertEqual(printed.call_args[0][0], "gpt-6.1-sol medium (standard postflight; codex vendor)")
            run_manifest.main(["route", "--role", "preflight-review", "--profile", "deep", "--ceiling", "Sonnet"])
            self.assertEqual(printed.call_args[0][0], "claude-sonnet-5-5 high (deep preflight; claude vendor)")

    def test_claude_takes_fable_for_opus_xhigh_within_the_ceiling(self) -> None:
        adaptive = run_dispatch.ceiling_policy(None)
        critical = run_dispatch.route("preflight-review", "critical")
        self.assertEqual(run_dispatch.resolve(*critical, "claude", adaptive)[:2], ("claude-fable-5-2", "high"))
        self.assertEqual(run_dispatch.resolve(*critical, "codex", adaptive)[:2], ("gpt-6.1-sol", "xhigh"))
        for ceiling in ("Opus", "Sol", "Terra"):
            model, effort, _ = run_dispatch.resolve(*critical, "claude", run_dispatch.ceiling_policy(ceiling))
            self.assertEqual((run_dispatch.capped(model, ceiling), effort),
                             (run_dispatch.capped("claude-opus-5-5", ceiling), "xhigh"))
        deep = run_dispatch.route("preflight-review", "deep")
        self.assertEqual(run_dispatch.resolve(*deep, "claude", adaptive)[:2], ("claude-opus-5-5", "high"))
        exceptional = run_dispatch.route("preflight-review", "exceptional")
        self.assertEqual(run_dispatch.resolve(*exceptional, "claude", adaptive)[:2], ("claude-fable-5-2", "high"))
        with patch.dict(os.environ, {"CLAUDECODE": "1", "CODEX_THREAD_ID": ""}), patch("builtins.print") as printed:
            run_manifest.main(["route", "--role", "preflight-review", "--profile", "critical"])
            self.assertEqual(printed.call_args[0][0], "claude-fable-5-2 high "
                             "(critical preflight; Fable in place of Opus xhigh; claude vendor)")
            run_manifest.main(["route", "--role", "preflight-review", "--profile", "critical", "--ceiling", "Opus"])
            self.assertEqual(printed.call_args[0][0], "claude-opus-5-5 xhigh (critical preflight; claude vendor)")

    def test_vendor(self) -> None:
        with patch.dict(os.environ, {"CLAUDECODE": "1", "CODEX_THREAD_ID": ""}):
            self.assertEqual(run_dispatch.target_vendor("postflight-review", "preflight", "auto"), "claude")
            self.assertEqual(run_dispatch.target_vendor("code-simplicity-review", "postflight", "auto"), "claude")
            self.assertEqual(run_dispatch.target_vendor("postflight-review", "preflight", "cross"), "codex")
            self.assertEqual(run_dispatch.target_vendor("code-simplicity-review", "postflight", "cross"), "codex")
            self.assertEqual(run_dispatch.target_vendor("preflight-review", "preflight", "cross"), "claude")
            self.assertEqual(run_dispatch.target_vendor("implementation-worker", "preflight", "codex"), "codex")
        with patch.dict(os.environ, {"CLAUDECODE": ""}):
            self.assertEqual(run_dispatch.target_vendor("postflight-review", "preflight", "auto"), "codex")
            self.assertEqual(run_dispatch.target_vendor("postflight-review", "preflight", "cross"), "claude")
            self.assertEqual(run_dispatch.target_vendor("preflight-review", "preflight", "claude"), "claude")
        self.assertEqual(run_dispatch.vendor_model("gpt-6.1-sol", "claude"), "claude-opus-5-5")
        self.assertEqual(run_dispatch.vendor_model("gpt-6.1-terra", "codex"), "gpt-6.1-terra")


class DispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "repo"
        self.workspace.mkdir()
        codex_home = self.root / "codex-home"
        (codex_home / "agents").mkdir(parents=True)
        for role in run_dispatch.ROLES:
            (codex_home / "agents" / f"{role}.toml").write_text(
                f'name = "{role}"\ndeveloper_instructions = """\nYou are {role}.\n"""\n'
            )
        rollout = codex_home / "sessions" / "rollout-thread-1.jsonl"
        rollout.parent.mkdir()
        items = [
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}},
            {"type": "turn_context", "payload": {"turn_id": "t1", "model": "gpt-6.1-sol"}},
            {"type": "response_item", "payload": {
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": "$develop-task E Terra fix it"}],
                "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
            }},
            {"type": "event_msg", "timestamp": "2026-11-09T10:00:00Z", "payload": {
                "type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 500, "cached_input_tokens": 400, "output_tokens": 9,
                    "reasoning_output_tokens": 3,
                }},
            }},
        ]
        rollout.write_text("".join(json.dumps(item) + "\n" for item in items))
        environment = patch.dict(os.environ, {
            "CODEX_THREAD_ID": "thread-1", "CODEX_HOME": str(codex_home), "CLAUDECODE": "",
            "CODEX_AGENT_RUNNER": "",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.runner = self.root / "fake-runner"
        self.runner.write_text(FAKE_RUNNER.format(python=sys.executable))
        self.runner.chmod(0o755)
        self.prompt = self.root / "packet.md"
        self.prompt.write_text("Goal: fix it.\n")
        self.run_path = run_manifest.init_manifest(str(self.workspace))
        self.addCleanup(shutil.rmtree, self.run_path.parent)

    def dispatch(self, **kwargs: object) -> tuple[int, dict[str, object]]:
        code, output = run_dispatch.dispatch(
            prompt_file=str(self.prompt), runner=str(self.runner), **kwargs
        )
        return code, yaml.safe_load(output)

    def test_dispatch_routes_caps_registers_runs_and_reconciles(self) -> None:
        code, summary = self.dispatch(
            role="preflight-review", profile="standard", run_manifest=str(self.run_path),
            contract_revision=1,
        )
        self.assertEqual(code, 0)
        self.assertEqual(summary["job"], "001-preflight")
        self.assertEqual(summary["requested_model"], "gpt-6.1-sol")
        self.assertEqual(summary["model"], "gpt-6.1-terra")
        self.assertEqual(summary["report"], "Decision: proceed")
        task = yaml.safe_load(Path(summary["task"]).read_text())
        self.assertEqual(task["permissions"]["sandbox_mode"], "read_only")
        self.assertEqual(task["supervision"]["max_attempts"], 3)
        self.assertIn("You are preflight-review.", task["agent"]["developer_instructions"])
        self.assertIn("universal structured output", task["agent"]["developer_instructions"])
        self.assertTrue(task["job"]["prompt"].startswith("Routing: standard profile, preflight-review, gpt-6.1-terra"))
        job = yaml.safe_load(self.run_path.read_text())["jobs"][0]
        self.assertEqual((job["status"], job["limited_by"]), ("completed", "explicit_ceiling"))

        code, summary = self.dispatch(
            role="implementation-worker", profile="standard", run_manifest=str(self.run_path),
            contract_revision=1, approved_by_preflight="001-preflight",
        )
        task = yaml.safe_load(Path(summary["task"]).read_text())
        self.assertEqual(summary["job"], "002-implementation")
        self.assertEqual(task["permissions"]["sandbox_mode"], "workspace_write")
        self.assertIn("universal `completed`", task["agent"]["developer_instructions"])

        table = run_dispatch.usage_table(str(self.run_path))
        self.assertIn("| 001-preflight | gpt-6.1-terra medium (capped from gpt-6.1-sol) | completed | 1 | 30 | 60 | 10 | 7 (2) |", table)
        self.assertIn("| Total: 2 jobs | | | 2 |", table)
        self.assertIn("| main | | | | 100 | 400 | 0 | 9 (3) |", table)

    def test_dispatch_rejects_unlinked_writer_and_bad_override(self) -> None:
        with self.assertRaisesRegex(run_manifest.ManifestError, "approved-by-preflight"):
            self.dispatch(role="implementation-worker", profile="fast",
                          run_manifest=str(self.run_path), contract_revision=1)
        with self.assertRaisesRegex(run_manifest.ManifestError, "reason"):
            self.dispatch(role="preflight-review", profile="fast", run_manifest=str(self.run_path),
                          contract_revision=1, model="gpt-6-astra", effort="high")
        with self.assertRaisesRegex(run_manifest.ManifestError, "contract-revision"):
            self.dispatch(role="preflight-review", profile="fast", run_manifest=str(self.run_path))
        with self.assertRaisesRegex(run_manifest.ManifestError, "ceiling"):
            self.dispatch(role="preflight-review", profile="fast", run_manifest=str(self.run_path),
                          contract_revision=1, ceiling="Luna")
        with self.assertRaisesRegex(run_manifest.ManifestError, "executable agent-runner"):
            run_dispatch.dispatch(prompt_file=str(self.prompt), runner="/nonexistent",
                                  role="preflight-review", profile="fast",
                                  run_manifest=str(self.run_path), contract_revision=1)
        self.assertEqual(yaml.safe_load(self.run_path.read_text())["jobs"], [])

    def test_dispatch_without_manifest_applies_ceiling_and_vendor(self) -> None:
        with patch.dict(os.environ, {"CLAUDECODE": "1", "CODEX_THREAD_ID": ""}):
            code, summary = self.dispatch(
                role="postflight-review", profile="deep", workspace=str(self.workspace),
                ceiling="Terra", vendor="cross",
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary["vendor"], "codex")
        self.assertEqual(summary["model"], "gpt-6.1-terra")
        self.assertEqual(Path(summary["task"]).parent.stat().st_mode & 0o777, 0o700)

    def test_refused_fable_job_reruns_on_opus_xhigh(self) -> None:
        with patch.dict(os.environ, {"CLAUDECODE": "1", "CODEX_THREAD_ID": "", "FAKE_REFUSE": "1"}):
            code, summary = self.dispatch(
                role="preflight-review", profile="critical", workspace=str(self.workspace),
            )
        self.assertEqual(code, 0)
        self.assertEqual((summary["model"], summary["effort"]), ("claude-opus-5-5", "xhigh"))
        self.assertEqual(summary["outcome_status"], "completed")
        self.assertEqual(summary["refused"]["model"], "claude-fable-5-2")
        task = yaml.safe_load(Path(summary["task"]).read_text())
        self.assertIn("stopped on a safety refusal", task["job"]["prompt"])
        self.assertIn("Goal: fix it.", task["job"]["prompt"])


if __name__ == "__main__":
    unittest.main()
