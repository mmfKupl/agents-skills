from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(job["approved_by_preflight"], "001-preflight")
        self.assertEqual(job["task_path"], str(expected))
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["model"], "gpt-5.6-luna")
        self.assertEqual(job["requested_model"], "gpt-5.6-luna")
        self.assertEqual(job["selected_model"], "gpt-5.6-luna")
        self.assertIsNone(job["limited_by"])
        self.assertEqual(job["reasoning_effort"], "medium")

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


if __name__ == "__main__":
    unittest.main()
