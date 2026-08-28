from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_manifest


class RunManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.job_dir = self.root / "jobs" / "001-preflight"
        self.job_dir.mkdir(parents=True)
        self.task_path = self.job_dir / "task.yaml"
        self.task_path.write_text("kind: agent-task\n", encoding="utf-8")
        self.manifest_path = self.root / "run.yaml"
        self.write_manifest()
        self.codex_home = self.root / "codex-home"
        self.rollout = self.codex_home / "sessions" / "rollout-source-thread.jsonl"
        self.rollout.parent.mkdir(parents=True)
        environment = patch.dict(os.environ, {
            "CODEX_THREAD_ID": "source-thread", "CODEX_HOME": str(self.codex_home),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.write_invocation()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest_value(self) -> dict[str, object]:
        return {
            "kind": "develop-task-run",
            "schema_version": 1,
            "run": {
                "id": "run-1",
                "backend": "runner",
                "workspace": str(self.root),
                "status": "running",
                "started_at": "2026-08-22T10:00:00.000Z",
                "finished_at": None,
            },
            "jobs": [
                {
                    "id": "001-preflight",
                    "role": "preflight-review",
                    "contract_revision": 1,
                    "approved_by_preflight": None,
                    "task_path": str(self.task_path),
                    "result_path": None,
                    "status": "pending",
                    "model": "gpt-test",
                    "reasoning_effort": "high",
                }
            ],
        }

    def write_manifest(self, value: dict[str, object] | None = None) -> None:
        self.manifest_path.write_text(
            yaml.safe_dump(value or self.manifest_value(), sort_keys=False), encoding="utf-8"
        )

    def write_task_source(
        self,
        job_id: str = "002-implementation",
        *,
        workspace: Path | None = None,
        model: str = "gpt-5.6-luna",
    ) -> Path:
        source_path = self.root / f"{job_id}-draft.yaml"
        task = {
            "kind": "agent-task",
            "schema_version": 2,
            "job": {"id": job_id, "prompt": "Perform the bounded job."},
            "workspace": {"cwd": str(workspace or self.root)},
            "agent": {"model": model, "reasoning_effort": "medium"},
            "permissions": {
                "sandbox_mode": "workspace_write",
                "approval_policy": "never",
                "network_access": False,
            },
            "supervision": {
                "context": {
                    "soft_limit_tokens": 155000,
                    "hard_limit_tokens": 180000,
                    "checkpoint_grace_seconds": 20,
                },
                "max_attempts": 2,
            },
        }
        source_path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")
        return source_path

    def write_result(
        self,
        status: str = "completed",
        *,
        task_hash: str | None = None,
        execution_id: str = "execution-1",
    ) -> Path:
        result_dir = self.job_dir / "results"
        result_dir.mkdir(exist_ok=True)
        result_path = result_dir / f"{execution_id}.yaml"
        result = {
            "kind": "agent-result",
            "schema_version": 1,
            "execution": {
                "id": execution_id,
                "status": status,
                "pid": 123,
                "started_at": "2026-08-22T10:00:01.000Z",
                "finished_at": "2026-08-22T10:00:02.000Z",
                "heartbeat_at": "2026-08-22T10:00:02.000Z",
            },
            "task": {
                "path": str(self.task_path),
                "sha256": task_hash or hashlib.sha256(self.task_path.read_bytes()).hexdigest(),
                "job_id": "001-preflight",
            },
            "runner": {},
            "effective_configuration": {},
            "attempts": [],
            "usage": {"total_tokens": 42},
            "outcome": {},
            "approval": {},
            "error": None,
        }
        result_path.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
        return result_path.resolve()

    def read_manifest(self) -> dict[str, object]:
        return yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))

    def write_invocation(
        self, message: str = "$develop-task UIB-test", *,
        model: str | None = "gpt-5.6-terra", turn_id: str = "turn-1", append: bool = False,
    ) -> None:
        items = [
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": turn_id}},
            {"type": "turn_context", "payload": {"turn_id": turn_id, "model": model}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                    "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
                },
            },
        ]
        with self.rollout.open("a" if append else "w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item) + "\n")

    def init_run(self, **kwargs: str) -> Path:
        path = run_manifest.init_manifest(str(self.root), **kwargs)
        self.addCleanup(shutil.rmtree, path.parent)
        return path

    def read_run(self, path: Path) -> dict:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_reconcile_marks_job_pending_without_result(self) -> None:
        run_manifest.reconcile_manifest(str(self.manifest_path))
        job = self.read_manifest()["jobs"][0]  # type: ignore[index]
        self.assertEqual(job["status"], "pending")
        self.assertIsNone(job["result_path"])
        self.assertIsNone(job["execution_id"])
        self.assertIsNone(job["usage"])

    def test_reconcile_copies_verified_execution_fields(self) -> None:
        result_path = self.write_result()
        run_manifest.reconcile_manifest(str(self.manifest_path))
        job = self.read_manifest()["jobs"][0]  # type: ignore[index]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["result_path"], str(result_path))
        self.assertEqual(job["execution_id"], "execution-1")
        self.assertEqual(job["usage"], {"total_tokens": 42})
        self.assertEqual(list(self.root.glob(".run.yaml.*.tmp")), [])

    def test_reconcile_rejects_tampered_task_hash_without_rewriting_manifest(self) -> None:
        self.write_result(task_hash="0" * 64)
        original = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(run_manifest.ManifestError, "hash"):
            run_manifest.reconcile_manifest(str(self.manifest_path))
        self.assertEqual(self.manifest_path.read_bytes(), original)

    def test_reconcile_rejects_multiple_executions_for_one_job(self) -> None:
        self.write_result(execution_id="execution-1")
        self.write_result(execution_id="execution-2")
        with self.assertRaisesRegex(run_manifest.ManifestError, "new job directory"):
            run_manifest.reconcile_manifest(str(self.manifest_path))

    def test_reconcile_records_invalid_task_without_worker_job_id(self) -> None:
        result_path = self.write_result(status="invalid_task")
        result = yaml.safe_load(result_path.read_text(encoding="utf-8"))
        result["task"]["job_id"] = None
        result_path.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
        run_manifest.reconcile_manifest(str(self.manifest_path))
        job = self.read_manifest()["jobs"][0]  # type: ignore[index]
        self.assertEqual(job["status"], "invalid_task")
        self.assertEqual(job["result_path"], str(result_path))

    def test_new_job_validates_creates_and_registers_task(self) -> None:
        source_path = self.write_task_source()
        task_path = run_manifest.new_job_manifest(
            str(self.manifest_path),
            str(source_path),
            "implementation-worker",
            1,
            "001-preflight",
        )

        expected = (self.root / "jobs" / "002-implementation" / "task.yaml").resolve()
        self.assertEqual(task_path, expected)
        self.assertEqual(task_path.read_bytes(), source_path.read_bytes())
        job = self.read_manifest()["jobs"][1]  # type: ignore[index]
        self.assertEqual(job["id"], "002-implementation")
        self.assertEqual(job["role"], "implementation-worker")
        self.assertEqual(job["requirements_revision"], 1)
        self.assertEqual(job["approved_by_preflight"], "001-preflight")
        self.assertEqual(job["task_path"], str(expected))
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["model"], "gpt-5.6-luna")
        self.assertEqual(job["requested_model"], "gpt-5.6-luna")
        self.assertEqual(job["selected_model"], "gpt-5.6-luna")
        self.assertIsNone(job["limited_by"])
        self.assertEqual(job["reasoning_effort"], "medium")

    def test_amendments_preserve_history_and_stamp_later_jobs(self) -> None:
        result_path = self.write_result()
        original_task = self.task_path.read_bytes()
        original_result = result_path.read_bytes()
        first = {
            "requirement_id": "R1",
            "before": "Temporary report files are permitted with cleanup.",
            "after": "Generate the report only in memory.",
            "source": "Developer message 12: generate it only in memory.",
            "reason": "Developer requested no temporary report files.",
        }
        run_manifest.amend_requirement_manifest(str(self.manifest_path), **first)
        source = self.write_task_source()
        task_path = run_manifest.new_job_manifest(
            str(self.manifest_path), str(source), "implementation-worker", 3, "001-preflight"
        )
        second = {
            **first,
            "requirement_id": "R2",
            "before": "Export CSV.",
            "after": "Export XLSX.",
            "source": "Developer message 13: use XLSX instead of CSV.",
        }
        run_manifest.amend_requirement_manifest(str(self.manifest_path), **second)

        manifest = self.read_manifest()
        self.assertEqual(
            manifest["run"]["requirements"],  # type: ignore[index]
            {"revision": 3, "amendments": [{**first, "revision": 2}, {**second, "revision": 3}]},
        )
        job = manifest["jobs"][1]  # type: ignore[index]
        self.assertEqual(job["requirements_revision"], 2)
        self.assertEqual(job["contract_revision"], 3)
        self.assertEqual(task_path.read_bytes(), source.read_bytes())
        self.assertEqual(self.task_path.read_bytes(), original_task)
        self.assertEqual(result_path.read_bytes(), original_result)

    def test_amendment_requires_a_source_without_rewriting_manifest(self) -> None:
        original = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(run_manifest.ManifestError, "source"):
            run_manifest.amend_requirement_manifest(
                str(self.manifest_path), "R1", "Before", "After", "", "Reason"
            )
        self.assertEqual(self.manifest_path.read_bytes(), original)

    def test_requirements_survive_finish_and_resume(self) -> None:
        self.write_result()
        run_manifest.amend_requirement_manifest(
            str(self.manifest_path), "R1", "Before", "After", "Developer message", "Reason"
        )
        requirements = self.read_manifest()["run"]["requirements"]  # type: ignore[index]
        run_manifest.finish_manifest(str(self.manifest_path), "needs_user_input")
        with self.assertRaisesRegex(run_manifest.ManifestError, "resume it first"):
            run_manifest.amend_requirement_manifest(
                str(self.manifest_path), "R1", "After", "Later", "Developer message", "Reason"
            )
        run_manifest.resume_manifest(str(self.manifest_path))
        self.assertEqual(
            self.read_manifest()["run"]["requirements"], requirements  # type: ignore[index]
        )

    def test_reconcile_rejects_incomplete_requirements_history(self) -> None:
        for requirements in (
            {"revision": 2, "amendments": []},
            {"revision": 1, "amendments": "not a list"},
            {"revision": 2, "amendments": [{"revision": 2}]},
        ):
            with self.subTest(requirements=requirements):
                manifest = self.manifest_value()
                manifest["run"]["requirements"] = requirements  # type: ignore[index]
                self.write_manifest(manifest)
                original = self.manifest_path.read_bytes()
                with self.assertRaises(run_manifest.ManifestError):
                    run_manifest.reconcile_manifest(str(self.manifest_path))
                self.assertEqual(self.manifest_path.read_bytes(), original)

    def test_reconcile_rejects_job_with_unrecorded_requirements_revision(self) -> None:
        manifest = self.manifest_value()
        manifest["jobs"][0]["requirements_revision"] = 2  # type: ignore[index]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(run_manifest.ManifestError, "recorded revision"):
            run_manifest.reconcile_manifest(str(self.manifest_path))

    def test_new_job_applies_explicit_ceiling_to_immutable_task(self) -> None:
        manifest = self.manifest_value()
        manifest["run"]["model_policy"] = {  # type: ignore[index]
            "mode": "explicit_ceiling",
            "maximum_model": "gpt-5.6-terra",
        }
        manifest["jobs"][0]["model"] = "gpt-5.6-terra"  # type: ignore[index]
        self.write_manifest(manifest)
        source_path = self.write_task_source(model="gpt-5.6-sol")

        task_path = run_manifest.new_job_manifest(
            str(self.manifest_path),
            str(source_path),
            "implementation-worker",
            1,
            "001-preflight",
        )

        source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        self.assertEqual(source["agent"]["model"], "gpt-5.6-sol")
        self.assertEqual(task["agent"]["model"], "gpt-5.6-terra")
        job = self.read_manifest()["jobs"][1]  # type: ignore[index]
        self.assertEqual(job["model"], "gpt-5.6-terra")
        self.assertEqual(job["requested_model"], "gpt-5.6-sol")
        self.assertEqual(job["selected_model"], "gpt-5.6-terra")
        self.assertEqual(job["limited_by"], "explicit_ceiling")

    def test_new_job_applies_main_ceiling_without_requesting_a_change(self) -> None:
        self.write_invocation("$develop-task M UIB-test", model="gpt-5.6-luna")
        manifest = self.manifest_value()
        manifest["run"]["model_policy"] = {  # type: ignore[index]
            "mode": "main_ceiling",
            "maximum_model": "gpt-5.6-luna",
        }
        manifest["jobs"][0]["model"] = "gpt-5.6-luna"  # type: ignore[index]
        self.write_manifest(manifest)
        source_path = self.write_task_source(model="gpt-5.6-sol")

        run_manifest.new_job_manifest(
            str(self.manifest_path),
            str(source_path),
            "implementation-worker",
            1,
            "001-preflight",
        )

        job = self.read_manifest()["jobs"][1]  # type: ignore[index]
        self.assertEqual(job["selected_model"], "gpt-5.6-luna")
        self.assertEqual(job["limited_by"], "main_ceiling")

    def test_init_infers_m_from_actual_desktop_invocation(self) -> None:
        message = (
            "[$develop-please](/repo/.codex/skills/develop-please/SKILL.md) + "
            "[$develop-task](/home/user/.codex/skills/develop-task/SKILL.md) M UIB-5340\n"
        )
        self.write_invocation(message)
        path = self.init_run()
        document = self.read_run(path)
        self.assertEqual(document["jobs"], [])
        self.assertEqual(document["run"]["model_policy"], {
            "mode": "main_ceiling", "maximum_model": "gpt-5.6-terra",
        })
        self.assertEqual(document["run"]["model_policy_source"], {
            "thread_id": "source-thread", "turn_id": "turn-1",
            "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
        })
        self.assertEqual(document["run"]["requirements"], {"revision": 1, "amendments": []})
        self.assertEqual(document["run"]["workspace"], str(self.root))
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertNotEqual(path, self.init_run())

    def test_init_rejects_adaptive_override_of_m_before_creating_directory(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        with patch.object(run_manifest.tempfile, "mkdtemp") as create_dir:
            with self.assertRaisesRegex(run_manifest.ManifestError, "requires main_ceiling"):
                self.init_run(mode="adaptive")
            create_dir.assert_not_called()

    def test_init_infers_explicit_ceiling_aliases(self) -> None:
        for parameter, maximum in (
            ("E Luna", "gpt-5.6-luna"),
            ("E: Terra", "gpt-5.6-terra"),
            ("E gpt-5.6-sol", "gpt-5.6-sol"),
            ("explicit_ceiling Luna", "gpt-5.6-luna"),
        ):
            with self.subTest(parameter=parameter):
                self.write_invocation(f"$develop-task {parameter} UIB-test")
                self.assertEqual(self.read_run(self.init_run())["run"]["model_policy"], {
                    "mode": "explicit_ceiling", "maximum_model": maximum,
                })

    def test_init_rejects_wrong_or_unresolvable_explicit_ceiling(self) -> None:
        self.write_invocation("$develop-task E Terra UIB-test")
        for kwargs in (
            {"mode": "adaptive"}, {"mode": "main_ceiling"}, {"maximum_model": "Sol"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(run_manifest.ManifestError, "contradicts source"):
                    self.init_run(**kwargs)
        for parameter in ("E", "E gpt-5.5", "E unknown"):
            with self.subTest(parameter=parameter):
                self.write_invocation(f"$develop-task {parameter}")
                with self.assertRaisesRegex(run_manifest.ManifestError, "source E requires"):
                    self.init_run()

    def test_init_preserves_adaptive_and_contextual_natural_language_resolution(self) -> None:
        self.assertEqual(self.read_run(self.init_run())["run"]["model_policy"], {
            "mode": "adaptive", "maximum_model": None,
        })
        self.write_invocation("$develop-task не используй сильные модели для этой задачи")
        self.assertEqual(
            self.read_run(self.init_run(mode="explicit_ceiling", maximum_model="Luna"))["run"]["model_policy"],
            {"mode": "explicit_ceiling", "maximum_model": "gpt-5.6-luna"},
        )
        self.write_invocation("$develop-task не выше собственной модели")
        self.assertEqual(self.read_run(self.init_run(mode="main_ceiling"))["run"]["model_policy"], {
            "mode": "main_ceiling", "maximum_model": "gpt-5.6-terra",
        })

    def test_init_pins_invocation_turn_not_latest_model_or_followup(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        self.write_invocation("окей делай так", model="gpt-5.6-sol", turn_id="turn-2", append=True)
        path = self.init_run()
        self.assertEqual(self.read_run(path)["run"]["model_policy"]["maximum_model"], "gpt-5.6-terra")
        self.assertEqual(self.read_run(path)["run"]["model_policy_source"]["turn_id"], "turn-1")

    def test_invocation_model_comes_from_turn_context_not_thread_settings(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        items = [json.loads(line) for line in self.rollout.read_text().splitlines()]
        items.insert(1, {"type": "world_state", "payload": {
            "state": {"model": "gpt-5.6-sol"},
        }})
        items.append({"type": "event_msg", "payload": {
            "type": "thread_settings_applied", "thread_settings": {"model": "gpt-5.6-sol"},
        }})
        self.rollout.write_text("\n".join(json.dumps(item) for item in items) + "\n")
        path = self.init_run()
        self.assertEqual(self.read_run(path)["run"]["model_policy"]["maximum_model"], "gpt-5.6-terra")
        source = self.write_task_source(model="gpt-5.6-sol")
        task_path = run_manifest.new_job_manifest(str(path), str(source), "preflight-review", 1, None)
        self.assertEqual(self.read_run(task_path)["agent"]["model"], "gpt-5.6-terra")

    def test_source_reader_handles_user_message_before_turn_context(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        items = [json.loads(line) for line in self.rollout.read_text().splitlines()]
        items[1], items[2] = items[2], items[1]
        self.rollout.write_text("\n".join(json.dumps(item) for item in items) + "\n")
        path = self.init_run()
        source = self.read_run(path)["run"]["model_policy_source"]
        self.assertEqual(run_manifest.resolve_invocation(source).model, "gpt-5.6-terra")

    def test_init_requires_recoverable_source_and_supported_main_model(self) -> None:
        for message, model in (
            ("No skill invocation", "gpt-5.6-terra"),
            ("$develop-task M UIB-test", "unknown"),
            ("$develop-task M UIB-test", None),
        ):
            with self.subTest(message=message, model=model):
                self.write_invocation(message, model=model)
                with patch.object(run_manifest.tempfile, "mkdtemp") as create_dir:
                    with self.assertRaises(run_manifest.ManifestError):
                        self.init_run()
                    create_dir.assert_not_called()

    def test_source_reader_ignores_injected_skill_and_quoted_examples(self) -> None:
        message = (
            "$develop-task change column M\n"
            "> $develop-task M quoted example\n"
            "```text\n$develop-task E Sol\n```\n"
            "The documentation contains `$develop-task M`."
        )
        self.write_invocation(message)
        self.write_invocation(
            "<skill>\n<name>develop-task</name>\n$develop-task E Sol\n</skill>",
            append=True,
        )
        with self.rollout.open("a", encoding="utf-8") as handle:
            for role in ("assistant", "developer", "tool"):
                handle.write(json.dumps({"type": "response_item", "payload": {
                    "type": "message", "role": role,
                    "content": [{"type": "input_text", "text": "$develop-task M"}],
                }}) + "\n")
        run = self.read_run(self.init_run())["run"]
        self.assertEqual(run["model_policy"], {"mode": "adaptive", "maximum_model": None})
        self.assertEqual(run["model_policy_source"]["message_sha256"], hashlib.sha256(message.encode()).hexdigest())

    def test_init_uses_latest_real_invocation_and_rejects_ambiguous_message(self) -> None:
        self.write_invocation("$develop-task M previous task")
        self.write_invocation("develop-task next task", turn_id="turn-2", append=True)
        self.assertEqual(self.read_run(self.init_run())["run"]["model_policy"]["mode"], "adaptive")
        self.write_invocation("$develop-task M\n$develop-task E Luna")
        with self.assertRaisesRegex(run_manifest.ManifestError, "one unquoted"):
            self.init_run()

    def test_new_job_rejects_manual_adaptive_manifest_when_user_requested_m(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        source = self.write_task_source(model="gpt-5.6-sol")
        original = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(run_manifest.ManifestError, "requires main_ceiling"):
            run_manifest.new_job_manifest(str(self.manifest_path), str(source), "preflight-review", 1, None)
        self.assertEqual(self.manifest_path.read_bytes(), original)
        self.assertFalse((self.root / "jobs" / "002-implementation").exists())

    def test_new_job_rejects_changed_policy_and_missing_or_changed_source(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        source = self.write_task_source(model="gpt-5.6-sol")
        for change in ("adaptive", "higher_ceiling", "missing_source", "wrong_hash", "wrong_turn"):
            with self.subTest(change=change):
                path = self.init_run()
                document = self.read_run(path)
                run = document["run"]
                if change in {"adaptive", "missing_source"}:
                    run["model_policy"] = {"mode": "adaptive", "maximum_model": None}
                    if change == "missing_source":
                        del run["model_policy_source"]
                elif change == "higher_ceiling":
                    run["model_policy"]["maximum_model"] = "gpt-5.6-sol"
                elif change == "wrong_hash":
                    run["model_policy_source"]["message_sha256"] = "0" * 64
                else:
                    run["model_policy_source"]["turn_id"] = "wrong-turn"
                path.write_text(yaml.safe_dump(document), encoding="utf-8")
                original = path.read_bytes()
                with self.assertRaises(run_manifest.ManifestError):
                    run_manifest.new_job_manifest(str(path), str(source), "preflight-review", 1, None)
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse((path.parent / "jobs").exists())

    def test_new_job_caps_all_roles_and_preserves_reasoning_and_requested_model(self) -> None:
        self.write_invocation("$develop-task E Luna UIB-test")
        path = self.init_run()
        for index, role in enumerate(("preflight-review", "implementation-worker", "postflight-review")):
            source = self.write_task_source(job_id=f"job-{index}", model="gpt-5.6-sol")
            task_path = run_manifest.new_job_manifest(str(path), str(source), role, 1, None)
            task = self.read_run(task_path)
            self.assertEqual(task["agent"], {"model": "gpt-5.6-luna", "reasoning_effort": "medium"})
            job = self.read_run(path)["jobs"][-1]
            self.assertEqual(job["requested_model"], "gpt-5.6-sol")
            self.assertEqual(job["selected_model"], "gpt-5.6-luna")
            self.assertEqual(job["limited_by"], "explicit_ceiling")

    def test_new_job_preserves_default_adaptive_routing(self) -> None:
        path = self.init_run()
        source = self.write_task_source(model="gpt-5.6-sol")
        task_path = run_manifest.new_job_manifest(str(path), str(source), "preflight-review", 1, None)
        self.assertEqual(self.read_run(task_path)["agent"]["model"], "gpt-5.6-sol")
        self.assertIsNone(self.read_run(path)["jobs"][0]["limited_by"])

    def test_resumed_run_keeps_original_source_even_after_new_invocation(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        path = self.init_run()
        original_source = self.read_run(path)["run"]["model_policy_source"]
        run_manifest.finish_manifest(str(path), "completed")
        self.write_invocation("$develop-task E Sol next task", model="gpt-5.6-sol", turn_id="turn-2", append=True)
        run_manifest.resume_manifest(str(path))
        source = self.write_task_source(model="gpt-5.6-sol")
        task_path = run_manifest.new_job_manifest(str(path), str(source), "preflight-review", 1, None)
        self.assertEqual(self.read_run(task_path)["agent"]["model"], "gpt-5.6-terra")
        self.assertEqual(self.read_run(path)["run"]["model_policy_source"], original_source)

    def test_new_job_requires_source_but_old_results_remain_readable(self) -> None:
        self.rollout.unlink()
        run_manifest.reconcile_manifest(str(self.manifest_path))
        source = self.write_task_source()
        original = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(run_manifest.ManifestError, "cannot find rollout"):
            run_manifest.new_job_manifest(str(self.manifest_path), str(source), "preflight-review", 1, None)
        self.assertEqual(self.manifest_path.read_bytes(), original)

    def test_new_job_binds_legacy_source_only_after_matching_policy(self) -> None:
        self.write_invocation("$develop-task E Terra UIB-test")
        manifest = self.manifest_value()
        manifest["run"]["model_policy"] = {  # type: ignore[index]
            "mode": "explicit_ceiling", "maximum_model": "gpt-5.6-terra",
        }
        manifest["jobs"][0]["model"] = "gpt-5.6-terra"  # type: ignore[index]
        self.write_manifest(manifest)
        source = self.write_task_source(model="gpt-5.6-sol")
        run_manifest.new_job_manifest(str(self.manifest_path), str(source), "preflight-review", 1, None)
        run = self.read_manifest()["run"]
        self.assertEqual(run["model_policy_source"]["turn_id"], "turn-1")  # type: ignore[index]

    def test_init_cli_prints_only_absolute_manifest_path(self) -> None:
        self.write_invocation("$develop-task M UIB-test")
        completed = subprocess.run(
            [sys.executable, str(Path(run_manifest.__file__).resolve()), "init", "--workspace", str(self.root)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        path = Path(completed.stdout.strip())
        self.addCleanup(shutil.rmtree, path.parent)
        self.assertTrue(path.is_absolute())
        self.assertEqual(self.read_run(path)["run"]["model_policy"]["maximum_model"], "gpt-5.6-terra")

    def test_new_job_rejects_model_outside_ceiling_order(self) -> None:
        manifest = self.manifest_value()
        manifest["run"]["model_policy"] = {  # type: ignore[index]
            "mode": "explicit_ceiling",
            "maximum_model": "gpt-5.6-terra",
        }
        manifest["jobs"][0]["model"] = "gpt-5.6-terra"  # type: ignore[index]
        self.write_manifest(manifest)
        source_path = self.write_task_source(model="gpt-5.5")
        original = self.manifest_path.read_bytes()

        with self.assertRaisesRegex(run_manifest.ManifestError, "unsupported requested model"):
            run_manifest.new_job_manifest(
                str(self.manifest_path),
                str(source_path),
                "implementation-worker",
                1,
                "001-preflight",
            )

        self.assertEqual(self.manifest_path.read_bytes(), original)
        self.assertFalse((self.root / "jobs" / "002-implementation").exists())

    def test_resume_preserves_model_policy(self) -> None:
        manifest = self.manifest_value()
        manifest["run"]["model_policy"] = {  # type: ignore[index]
            "mode": "explicit_ceiling",
            "maximum_model": "gpt-5.6-terra",
        }
        manifest["jobs"][0]["model"] = "gpt-5.6-terra"  # type: ignore[index]
        self.write_manifest(manifest)
        self.write_result()
        run_manifest.finish_manifest(str(self.manifest_path), "completed")

        run_manifest.resume_manifest(str(self.manifest_path))

        resumed = self.read_manifest()
        self.assertEqual(
            resumed["run"]["model_policy"],  # type: ignore[index]
            {
                "mode": "explicit_ceiling",
                "maximum_model": "gpt-5.6-terra",
            },
        )

    def test_resolve_main_model_reads_latest_turn_context(self) -> None:
        codex_home = self.root / "codex-home"
        rollout_dir = codex_home / "sessions" / "2026" / "08" / "26"
        rollout_dir.mkdir(parents=True)
        rollout = rollout_dir / "rollout-thread-123.jsonl"
        items = [
            {
                "type": "turn_context",
                "payload": {"model": "gpt-5.6-luna"},
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "thread_settings_applied",
                    "thread_settings": {"model": "gpt-5.6-terra"},
                },
            },
            {
                "type": "turn_context",
                "payload": {"model": "gpt-5.6-sol"},
            },
        ]
        rollout.write_text(
            "\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8"
        )

        self.assertEqual(
            run_manifest.resolve_main_model("thread-123", codex_home),
            "gpt-5.6-sol",
        )

    def test_new_job_rejects_invalid_task_without_changing_manifest(self) -> None:
        source_path = self.root / "invalid-draft.yaml"
        source_path.write_text("kind: agent-task\n", encoding="utf-8")
        original = self.manifest_path.read_bytes()

        with self.assertRaisesRegex(run_manifest.ManifestError, "invalid task source"):
            run_manifest.new_job_manifest(
                str(self.manifest_path),
                str(source_path),
                "implementation-worker",
                1,
                "001-preflight",
            )

        self.assertEqual(self.manifest_path.read_bytes(), original)
        self.assertFalse((self.root / "jobs" / "002-implementation").exists())

    def test_finish_refuses_active_jobs(self) -> None:
        with self.assertRaisesRegex(run_manifest.ManifestError, "active jobs"):
            run_manifest.finish_manifest(str(self.manifest_path), "completed")
        self.assertEqual(self.read_manifest()["run"]["status"], "running")  # type: ignore[index]

    def test_finish_refuses_unregistered_task_file(self) -> None:
        self.write_result()
        unregistered_dir = self.root / "jobs" / "002-unregistered"
        unregistered_dir.mkdir()
        (unregistered_dir / "task.yaml").write_text("kind: agent-task\n", encoding="utf-8")

        with self.assertRaisesRegex(run_manifest.ManifestError, "unregistered task files"):
            run_manifest.finish_manifest(str(self.manifest_path), "completed")

        self.assertEqual(self.read_manifest()["run"]["status"], "running")  # type: ignore[index]

    def test_finish_and_resume_update_run_lifecycle(self) -> None:
        self.write_result()
        run_manifest.finish_manifest(str(self.manifest_path), "completed")
        finished = self.read_manifest()
        self.assertEqual(finished["run"]["status"], "completed")  # type: ignore[index]
        self.assertIsNotNone(finished["run"]["finished_at"])  # type: ignore[index]

        run_manifest.resume_manifest(str(self.manifest_path))
        resumed = self.read_manifest()
        self.assertEqual(resumed["run"]["status"], "running")  # type: ignore[index]
        self.assertIsNone(resumed["run"]["finished_at"])  # type: ignore[index]

    def test_cli_prints_only_absolute_manifest_path(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(run_manifest.__file__).resolve()),
                "reconcile",
                str(self.manifest_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), str(self.manifest_path))
        self.assertEqual(completed.stderr, "")

    def test_new_job_cli_prints_only_absolute_task_path(self) -> None:
        source_path = self.write_task_source()
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(run_manifest.__file__).resolve()),
                "new-job",
                str(self.manifest_path),
                str(source_path),
                "--role",
                "implementation-worker",
                "--contract-revision",
                "1",
                "--approved-by-preflight",
                "001-preflight",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        expected = self.root / "jobs" / "002-implementation" / "task.yaml"
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), str(expected))
        self.assertEqual(completed.stderr, "")

    def test_amendment_cli_preserves_exact_text(self) -> None:
        before = "Seven sheets.\nKeep their original names."
        after = "Eight sheets.\nAdd Credit Ledger."
        source = "Developer message 42: Добавь восьмой лист Credit Ledger."
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(run_manifest.__file__).resolve()),
                "amend-requirement",
                str(self.manifest_path),
                "R1",
                "--before", before,
                "--after", after,
                "--source", source,
                "--reason", "The developer requested a complete ledger.",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), str(self.manifest_path))
        self.assertEqual(completed.stderr, "")
        amendment = self.read_manifest()["run"]["requirements"]["amendments"][0]  # type: ignore[index]
        self.assertEqual(amendment["before"], before)
        self.assertEqual(amendment["after"], after)
        self.assertEqual(amendment["source"], source)


if __name__ == "__main__":
    unittest.main()
