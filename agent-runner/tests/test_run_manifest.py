from __future__ import annotations

import hashlib
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

    def test_finish_refuses_active_jobs(self) -> None:
        with self.assertRaisesRegex(run_manifest.ManifestError, "active jobs"):
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


if __name__ == "__main__":
    unittest.main()
