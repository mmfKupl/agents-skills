from __future__ import annotations

import hashlib
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_runner as runner


def worker_output(status: str = "completed", **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "status": status,
        "summary": "summary",
        "report": "report",
        "completed": ["done"],
        "remaining": [],
        "changed_files": [],
        "artifacts": [],
        "validation": [
            {"command": "python -m unittest", "status": "passed", "summary": "ok"}
        ],
        "warnings": [],
        "questions": [],
    }
    value.update(updates)
    return value


def event(method: str, payload: object) -> SimpleNamespace:
    return SimpleNamespace(method=method, payload=payload)


def usage_event(
    last_total: int,
    window: int | None = 100,
    input_tokens: int | None = None,
    accumulated_total: int | None = None,
) -> SimpleNamespace:
    last_breakdown = SimpleNamespace(
        input_tokens=last_total if input_tokens is None else input_tokens,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        output_tokens=0,
        reasoning_output_tokens=0,
        total_tokens=last_total,
    )
    total = last_total if accumulated_total is None else accumulated_total
    total_breakdown = SimpleNamespace(
        input_tokens=total if input_tokens is None else input_tokens,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        output_tokens=0,
        reasoning_output_tokens=0,
        total_tokens=total,
    )
    usage = SimpleNamespace(
        last=last_breakdown,
        total=total_breakdown,
        model_context_window=window,
    )
    return event("thread/tokenUsage/updated", SimpleNamespace(token_usage=usage))


def message_event(value: dict[str, object]) -> SimpleNamespace:
    item = SimpleNamespace(
        root=SimpleNamespace(type="agentMessage", phase="final_answer", text=json.dumps(value))
    )
    return event("item/completed", SimpleNamespace(item=item))


def delta_event(text: str) -> SimpleNamespace:
    return event("item/agentMessage/delta", SimpleNamespace(delta=text))


def completed_event(status: str = "completed", error: str | None = None) -> SimpleNamespace:
    error_value = SimpleNamespace(message=error) if error else None
    turn = SimpleNamespace(status=SimpleNamespace(value=status), error=error_value)
    return event("turn/completed", SimpleNamespace(turn=turn))


class FakeTurn:
    def __init__(
        self,
        turn_id: str,
        events: list[SimpleNamespace],
        *,
        stall: bool = False,
        complete_on_interrupt: bool = False,
        on_stream: object = None,
    ) -> None:
        self.id = turn_id
        self.events = events
        self.stall = stall
        self.complete_on_interrupt = complete_on_interrupt
        self.on_stream = on_stream
        self.steer_inputs: list[str] = []
        self.interrupt_count = 0

    async def steer(self, value: str) -> None:
        self.steer_inputs.append(value)

    async def interrupt(self) -> None:
        self.interrupt_count += 1

    async def stream(self):
        if self.on_stream:
            self.on_stream()
        for item in self.events:
            yield item
        if self.complete_on_interrupt:
            while self.interrupt_count == 0:
                await asyncio.sleep(0.001)
            yield completed_event("interrupted")
        if self.stall:
            await asyncio.Event().wait()


class FakeThread:
    def __init__(self, thread_id: str, turn: FakeTurn, owner: "FakeCodex") -> None:
        self.id = thread_id
        self._turn = turn
        self._owner = owner

    async def turn(self, prompt: str, **kwargs: object) -> FakeTurn:
        self._owner.turn_calls.append((prompt, kwargs))
        return self._turn


class FakeCodex:
    def __init__(
        self,
        config: object,
        scenarios: list[dict[str, object]],
        *,
        enter_error: Exception | None = None,
        on_enter: object = None,
    ) -> None:
        self.config = config
        self.scenarios = list(scenarios)
        self.enter_error = enter_error
        self.on_enter = on_enter
        self.thread_calls: list[dict[str, object]] = []
        self.turn_calls: list[tuple[str, dict[str, object]]] = []
        self.turns: list[FakeTurn] = []
        self.closed = False

    async def __aenter__(self) -> "FakeCodex":
        if self.on_enter:
            self.on_enter()
        if self.enter_error:
            raise self.enter_error
        return self

    async def thread_start(self, **kwargs: object) -> FakeThread:
        index = len(self.thread_calls) + 1
        self.thread_calls.append(kwargs)
        scenario = self.scenarios.pop(0)
        turn = FakeTurn(
            f"turn-{index}",
            scenario.get("events", []),
            stall=bool(scenario.get("stall", False)),
            complete_on_interrupt=bool(scenario.get("complete_on_interrupt", False)),
            on_stream=scenario.get("on_stream"),
        )
        self.turns.append(turn)
        return FakeThread(f"thread-{index}", turn, self)

    async def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self, scenarios: list[dict[str, object]], **kwargs: object) -> None:
        self.scenarios = scenarios
        self.kwargs = kwargs
        self.instances: list[FakeCodex] = []

    def __call__(self, config: object) -> FakeCodex:
        instance = FakeCodex(config, self.scenarios, **self.kwargs)
        self.instances.append(instance)
        return instance


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def task_value(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "kind": "agent-task",
            "schema_version": 2,
            "job": {"id": "job-1", "prompt": "Do one focused thing."},
            "workspace": {"cwd": str(self.workspace)},
            "agent": {"model": "gpt-test", "reasoning_effort": "high"},
            "permissions": {
                "sandbox_mode": "read_only",
                "approval_policy": "never",
                "network_access": False,
            },
            "supervision": {
                "context": {
                    "soft_limit_tokens": 60,
                    "hard_limit_tokens": 70,
                    "checkpoint_grace_seconds": 1,
                },
                "max_attempts": 2,
            },
        }
        value.update(updates)
        return value

    def write_task(self, value: dict[str, object] | None = None, name: str = "task.yaml") -> Path:
        path = self.root / name
        path.write_text(yaml.safe_dump(value or self.task_value(), sort_keys=False), encoding="utf-8")
        return path

    def run_with(self, scenarios: list[dict[str, object]], **kwargs: object):
        path = self.write_task(kwargs.pop("task", None))
        factory = Factory(scenarios, **kwargs)
        invocation = runner.run_invocation(str(path), sdk_factory=factory)
        result = yaml.safe_load(invocation.path.read_text(encoding="utf-8"))
        return invocation, result, factory.instances[0], path


class ValidationTests(RunnerTestCase):
    def test_valid_task_and_duplicate_keys(self) -> None:
        path = self.write_task()
        parsed = runner.parse_task(path.read_bytes(), path)
        self.assertEqual(parsed["kind"], "agent-task")
        with self.assertRaisesRegex(runner.TaskValidationError, "duplicate YAML key"):
            runner.parse_task(b"kind: one\nkind: two\n", path)

    def test_supported_context_threshold_pairs(self) -> None:
        for soft, hard in (
            (155_000, 180_000),
            (210_000, 240_000),
            (350_000, 400_000),
        ):
            value = self.task_value()
            value["supervision"]["context"].update(  # type: ignore[index,union-attr]
                {"soft_limit_tokens": soft, "hard_limit_tokens": hard}
            )
            with self.subTest(soft=soft, hard=hard):
                parsed = runner.parse_task(
                    yaml.safe_dump(value).encode(), self.root / "task.yaml"
                )
                self.assertEqual(
                    parsed["supervision"]["context"]["hard_limit_tokens"], hard
                )

    def test_unknown_keys_are_rejected_at_each_level(self) -> None:
        cases = []
        root = self.task_value()
        root["extra"] = True
        cases.append(root)
        nested = self.task_value()
        nested["agent"]["extra"] = True  # type: ignore[index]
        cases.append(nested)
        context = self.task_value()
        context["supervision"]["context"]["extra"] = True  # type: ignore[index]
        cases.append(context)
        removed_timeout = self.task_value()
        removed_timeout["supervision"]["timeout_seconds"] = 5  # type: ignore[index]
        cases.append(removed_timeout)
        for value in cases:
            with self.subTest(value=value):
                raw = yaml.safe_dump(value).encode()
                with self.assertRaisesRegex(runner.TaskValidationError, "unknown"):
                    runner.parse_task(raw, self.root / "task.yaml")

    def test_invariants_and_types_are_strict(self) -> None:
        mutations = [
            (lambda value: value.__setitem__("schema_version", True), "schema_version"),
            (lambda value: value.__setitem__("schema_version", 1.0), "schema_version"),
            (lambda value: value.__setitem__("schema_version", 1), "schema_version"),
            (
                lambda value: value["workspace"].__setitem__("cwd", "relative"),  # type: ignore[union-attr]
                "absolute",
            ),
            (
                lambda value: value["permissions"].__setitem__("approval_policy", "on_request"),  # type: ignore[union-attr]
                "never",
            ),
            (
                lambda value: value["supervision"]["context"].__setitem__("hard_limit_tokens", 60),  # type: ignore[index,union-attr]
                "0 < soft < hard",
            ),
            (
                lambda value: value["supervision"]["context"].__setitem__("soft_limit_tokens", 65),  # type: ignore[index,union-attr]
                "10% to 15%",
            ),
            (
                lambda value: value["supervision"]["context"].__setitem__("hard_limit_tokens", 70.0),  # type: ignore[index,union-attr]
                "positive integer",
            ),
            (
                lambda value: value["supervision"].__setitem__("max_attempts", True),  # type: ignore[union-attr]
                "positive integer",
            ),
        ]
        for mutation, expected in mutations:
            value = self.task_value()
            mutation(value)
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(runner.TaskValidationError, expected):
                    runner.parse_task(yaml.safe_dump(value).encode(), self.root / "task.yaml")

    def test_unsupported_network_combinations_are_rejected(self) -> None:
        for sandbox, network in (
            ("read_only", True),
            ("workspace_write", True),
            ("danger_full_access", False),
        ):
            value = self.task_value()
            value["permissions"].update(  # type: ignore[union-attr]
                {"sandbox_mode": sandbox, "network_access": network}
            )
            with self.subTest(sandbox=sandbox):
                with self.assertRaises(runner.TaskValidationError):
                    runner.parse_task(yaml.safe_dump(value).encode(), self.root / "task.yaml")

    def test_worker_output_is_universal_and_strict(self) -> None:
        self.assertEqual(runner.validate_worker_output(worker_output())["status"], "completed")
        invalid = worker_output()
        invalid["surprise"] = []
        with self.assertRaisesRegex(runner.TaskValidationError, "unknown"):
            runner.validate_worker_output(invalid)
        invalid_validation = worker_output(validation=[{"command": "x", "status": "ok"}])
        with self.assertRaisesRegex(runner.TaskValidationError, "missing"):
            runner.validate_worker_output(invalid_validation)


class ResultAndSdkTests(RunnerTestCase):
    def test_agent_message_deltas_use_rate_limited_result_heartbeats(self) -> None:
        writes = 0
        original_write = runner.AtomicResultWriter.write

        def counting_write(writer: runner.AtomicResultWriter, result: dict[str, object]) -> None:
            nonlocal writes
            writes += 1
            original_write(writer, result)  # type: ignore[arg-type]

        events = [delta_event("x") for _ in range(100)]
        events.extend([message_event(worker_output()), completed_event()])
        with mock.patch.object(runner.AtomicResultWriter, "write", new=counting_write):
            invocation, _, _, _ = self.run_with([{"events": events}])
        self.assertEqual(invocation.status, "completed")
        self.assertLess(writes, 20)

    def test_task_hash_nonmutation_unique_results_and_early_running(self) -> None:
        path = self.write_task()
        original = path.read_bytes()
        observed_statuses: list[str] = []

        def on_enter() -> None:
            result_paths = list((self.root / "results").glob("*.yaml"))
            observed_statuses.append(yaml.safe_load(result_paths[-1].read_text())["execution"]["status"])

        scenario = [{"events": [message_event(worker_output()), completed_event()]}]
        first_factory = Factory(scenario, on_enter=on_enter)
        first = runner.run_invocation(str(path), sdk_factory=first_factory)
        second_factory = Factory(
            [{"events": [message_event(worker_output()), completed_event()]}]
        )
        second = runner.run_invocation(str(path), sdk_factory=second_factory)
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(observed_statuses, ["running"])
        self.assertEqual(path.read_bytes(), original)
        first_result = yaml.safe_load(first.path.read_text())
        self.assertEqual(first_result["task"]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertFalse(list((self.root / "results").glob(".*.tmp")))

    def test_exact_read_only_sdk_mapping_and_deny_all_at_both_boundaries(self) -> None:
        invocation, result, codex, _ = self.run_with(
            [{"events": [message_event(worker_output()), completed_event()]}]
        )
        self.assertEqual(invocation.status, "completed")
        self.assertEqual(codex.config.config_overrides, ("agents.enabled=false",))
        self.assertEqual(len(codex.thread_calls), 1)
        thread_call = codex.thread_calls[0]
        self.assertIs(thread_call["approval_mode"], runner.ApprovalMode.deny_all)
        self.assertIs(thread_call["sandbox"], runner.Sandbox.read_only)
        self.assertTrue(thread_call["ephemeral"])
        self.assertEqual(thread_call["model"], "gpt-test")
        self.assertEqual(thread_call["cwd"], str(self.workspace))
        self.assertIn("Do not create subagents", thread_call["developer_instructions"])
        prompt, turn_call = codex.turn_calls[0]
        self.assertIn("Do one focused thing", prompt)
        self.assertIs(turn_call["approval_mode"], runner.ApprovalMode.deny_all)
        self.assertIs(turn_call["sandbox"], runner.Sandbox.read_only)
        self.assertEqual(turn_call["effort"], "high")
        self.assertIs(turn_call["output_schema"], runner.WORKER_OUTPUT_SCHEMA)
        self.assertEqual(result["approval"]["requested"], False)
        self.assertTrue(codex.closed)

    def test_workspace_and_full_access_mappings(self) -> None:
        workspace_task = self.task_value()
        workspace_task["permissions"].update(  # type: ignore[union-attr]
            {"sandbox_mode": "workspace_write", "network_access": False}
        )
        _, _, codex, _ = self.run_with(
            [{"events": [message_event(worker_output()), completed_event()]}],
            task=workspace_task,
        )
        self.assertEqual(codex.config.config_overrides, ("agents.enabled=false",))
        self.assertIs(codex.thread_calls[0]["sandbox"], runner.Sandbox.workspace_write)

        full_task = self.task_value()
        full_task["permissions"].update(  # type: ignore[union-attr]
            {"sandbox_mode": "danger_full_access", "network_access": True}
        )
        _, _, full_codex, _ = self.run_with(
            [{"events": [message_event(worker_output()), completed_event()]}],
            task=full_task,
        )
        self.assertEqual(full_codex.config.config_overrides, ("agents.enabled=false",))
        self.assertIs(full_codex.thread_calls[0]["sandbox"], runner.Sandbox.full_access)

    def test_invalid_task_still_has_structurally_valid_result_without_sdk(self) -> None:
        path = self.write_task({"kind": "wrong"})
        factory = Factory([])
        invocation = runner.run_invocation(str(path), sdk_factory=factory)
        result = yaml.safe_load(invocation.path.read_text())
        self.assertEqual(invocation.status, "invalid_task")
        self.assertEqual(result["kind"], "agent-result")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["execution"]["status"], "invalid_task")
        self.assertIsNotNone(result["execution"]["finished_at"])
        self.assertEqual(factory.instances, [])


class SupervisionTests(RunnerTestCase):
    def test_only_last_turn_usage_controls_context_pressure(self) -> None:
        scenarios = [
            {
                "events": [
                    usage_event(50, accumulated_total=95),
                    message_event(worker_output()),
                    completed_event(),
                ]
            }
        ]
        invocation, result, codex, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "completed")
        self.assertEqual(result["attempts"][0]["context_peak_tokens"], 50)
        self.assertEqual(result["attempts"][0]["context_peak_percent"], 50.0)
        self.assertEqual(codex.turns[0].steer_inputs, [])
        self.assertEqual(codex.turns[0].interrupt_count, 0)

    def test_checkpoint_rotates_to_fresh_ephemeral_thread_with_only_handoff(self) -> None:
        checkpoint = worker_output(
            "checkpoint", summary="checkpoint summary", remaining=["finish it"]
        )
        scenarios = [
            {
                "events": [
                    usage_event(75),
                    message_event(checkpoint),
                    completed_event(),
                ]
            },
            {
                "events": [
                    usage_event(20),
                    message_event(worker_output()),
                    completed_event(),
                ]
            },
        ]
        invocation, result, codex, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "completed")
        self.assertEqual([call["ephemeral"] for call in codex.thread_calls], [True, True])
        self.assertEqual([a["thread_id"] for a in result["attempts"]], ["thread-1", "thread-2"])
        self.assertEqual(codex.turns[0].steer_inputs, [runner.CHECKPOINT_STEER])
        second_prompt = codex.turn_calls[1][0]
        self.assertIn("structured_checkpoint", second_prompt)
        self.assertIn("checkpoint summary", second_prompt)
        self.assertNotIn("dialogue history", json.dumps(checkpoint))
        self.assertEqual(result["attempts"][0]["checkpoint"]["status"], "checkpoint")

    def test_hard_limit_interrupts_then_rotates_after_terminal(self) -> None:
        scenarios = [
            {
                "events": [
                    delta_event("partial durable work"),
                    usage_event(95, window=None),
                    completed_event("interrupted"),
                ]
            },
            {"events": [message_event(worker_output()), completed_event()]},
        ]
        invocation, result, codex, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "completed")
        self.assertEqual(codex.turns[0].interrupt_count, 1)
        self.assertEqual(codex.turns[0].steer_inputs, [runner.CHECKPOINT_STEER])
        self.assertEqual(result["attempts"][0]["context_peak_tokens"], 95)
        self.assertEqual(result["attempts"][0]["context_peak_percent"], 0.0)
        self.assertEqual(result["attempts"][0]["status"], "interrupted_for_context")
        self.assertIn("partial durable work", codex.turn_calls[1][0])

    def test_failed_terminal_status_overrides_valid_completed_output(self) -> None:
        scenarios = [
            {
                "events": [
                    message_event(worker_output()),
                    completed_event("failed", "terminal failure"),
                ]
            }
        ]
        invocation, result, _, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "failed")
        self.assertIsNone(result["outcome"])
        self.assertEqual(result["attempts"][0]["status"], "failed")
        self.assertIn("terminal failure", result["error"]["message"])

    def test_unexpected_interrupted_status_overrides_completed_output(self) -> None:
        scenarios = [
            {"events": [message_event(worker_output()), completed_event("interrupted")]}
        ]
        invocation, result, _, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "interrupted")
        self.assertIsNone(result["outcome"])
        self.assertEqual(result["attempts"][0]["status"], "interrupted")

    def test_context_interrupted_completed_output_is_only_fallback_carry(self) -> None:
        task = self.task_value()
        task["supervision"]["max_attempts"] = 1  # type: ignore[index]
        scenarios = [
            {
                "events": [
                    usage_event(95),
                    message_event(worker_output()),
                    completed_event("interrupted"),
                ]
            }
        ]
        invocation, result, _, _ = self.run_with(scenarios, task=task)
        self.assertEqual(invocation.status, "context_exhausted")
        self.assertIsNone(result["outcome"])
        self.assertEqual(
            result["attempts"][0]["checkpoint"]["kind"],
            "fallback_partial_agent_output",
        )

    def test_context_interrupted_checkpoint_is_rotation_carry_only(self) -> None:
        checkpoint = worker_output(
            "checkpoint", summary="safe handoff", remaining=["continue"]
        )
        scenarios = [
            {
                "events": [
                    usage_event(95),
                    message_event(checkpoint),
                    completed_event("interrupted"),
                ]
            },
            {"events": [message_event(worker_output()), completed_event()]},
        ]
        invocation, result, codex, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "completed")
        self.assertEqual(result["attempts"][0]["status"], "interrupted_for_context")
        self.assertEqual(result["attempts"][0]["checkpoint"]["status"], "checkpoint")
        self.assertIn("safe handoff", codex.turn_calls[1][0])
        self.assertEqual(result["outcome"]["status"], "completed")

    def test_checkpoint_grace_interrupts_and_waits_for_terminal_before_rotation(self) -> None:
        task = self.task_value()
        task["supervision"]["context"]["checkpoint_grace_seconds"] = 0.02  # type: ignore[index]
        scenarios = [
            {"events": [usage_event(65)], "complete_on_interrupt": True},
            {"events": [message_event(worker_output()), completed_event()]},
        ]
        invocation, result, codex, _ = self.run_with(scenarios, task=task)
        self.assertEqual(invocation.status, "completed")
        self.assertEqual(codex.turns[0].interrupt_count, 1)
        self.assertEqual(result["attempts"][0]["status"], "interrupted_for_context")
        self.assertEqual(len(codex.thread_calls), 2)

    def test_nonterminal_context_interrupt_does_not_start_next_attempt(self) -> None:
        scenarios = [
            {"events": [usage_event(95)]},
            {"events": [message_event(worker_output()), completed_event()]},
        ]
        invocation, result, codex, _ = self.run_with(scenarios)
        self.assertEqual(invocation.status, "failed")
        self.assertEqual(len(codex.thread_calls), 1)
        self.assertEqual(result["attempts"][0]["status"], "failed")

    def test_max_attempts_yields_context_exhausted(self) -> None:
        task = self.task_value()
        task["supervision"]["max_attempts"] = 2  # type: ignore[index]
        scenarios = [
            {"events": [usage_event(95), completed_event("interrupted")]},
            {"events": [usage_event(95), completed_event("interrupted")]},
        ]
        invocation, result, codex, _ = self.run_with(scenarios, task=task)
        self.assertEqual(invocation.status, "context_exhausted")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(len(codex.thread_calls), 2)
        self.assertEqual(result["error"]["type"], "context_exhausted")

    def test_usage_is_aggregated_from_final_attempt_totals(self) -> None:
        first = worker_output("checkpoint", remaining=["continue"])
        scenarios = [
            {"events": [usage_event(40, input_tokens=40), message_event(first), completed_event()]},
            {"events": [usage_event(30, input_tokens=30), message_event(worker_output()), completed_event()]},
        ]
        _, result, _, _ = self.run_with(scenarios)
        self.assertEqual(result["usage"]["input_tokens"], 70)
        self.assertEqual(result["usage"]["total_tokens"], 70)
        self.assertEqual(result["attempts"][0]["context_peak_tokens"], 40)
        self.assertEqual(result["attempts"][0]["context_peak_percent"], 40.0)

    def test_signal_interrupts_active_turn_and_closes_sdk(self) -> None:
        state = runner.SignalState()

        def trigger() -> None:
            state.triggered = "SIGTERM"

        path = self.write_task()
        factory = Factory([{"events": [], "stall": True, "on_stream": trigger}])
        invocation = runner.run_invocation(str(path), sdk_factory=factory, signals=state)
        result = yaml.safe_load(invocation.path.read_text())
        codex = factory.instances[0]
        self.assertEqual(invocation.status, "interrupted")
        self.assertEqual(result["error"]["message"], "received SIGTERM")
        self.assertEqual(codex.turns[0].interrupt_count, 1)
        self.assertTrue(codex.closed)

    def test_sdk_initialization_error_closes_and_finalizes(self) -> None:
        path = self.write_task()
        factory = Factory([], enter_error=RuntimeError("no auth"))
        invocation = runner.run_invocation(str(path), sdk_factory=factory)
        result = yaml.safe_load(invocation.path.read_text())
        self.assertEqual(invocation.status, "failed")
        self.assertIn("no auth", result["error"]["message"])
        self.assertTrue(factory.instances[0].closed)

    def test_sdk_factory_constructor_error_finalizes_existing_result(self) -> None:
        path = self.write_task()

        def broken_factory(_config: object) -> FakeCodex:
            raise RuntimeError("constructor failed")

        invocation = runner.run_invocation(str(path), sdk_factory=broken_factory)
        result = yaml.safe_load(invocation.path.read_text())
        self.assertEqual(invocation.status, "failed")
        self.assertEqual(result["execution"]["status"], "failed")
        self.assertIn("constructor failed", result["error"]["message"])


class LockAndCliTests(RunnerTestCase):
    def wait_for_path(self, path: Path, process: subprocess.Popen[str]) -> None:
        deadline = time.monotonic() + 5
        while not path.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(f"fixture exited early: {stdout=} {stderr=}")
            time.sleep(0.01)
        self.assertTrue(path.exists(), f"fixture did not create {path}")

    def test_subprocess_sigterm_finalizes_result(self) -> None:
        path = self.write_task()
        ready = self.root / "signal-ready"
        fixture = Path(__file__).with_name("subprocess_fixture.py")
        process = subprocess.Popen(
            [sys.executable, str(fixture), "signal", str(path), str(ready)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.wait_for_path(ready, process)
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        self.assertEqual(process.returncode, 0, stderr)
        result_path = Path(stdout.strip())
        result = yaml.safe_load(result_path.read_text())
        self.assertEqual(result["execution"]["status"], "interrupted")
        self.assertIsNotNone(result["execution"]["finished_at"])
        self.assertEqual(result["error"]["type"], "signal")

    def test_cross_process_write_lock_contention_finalizes_result(self) -> None:
        task = self.task_value()
        task["permissions"].update(  # type: ignore[union-attr]
            {"sandbox_mode": "workspace_write", "network_access": False}
        )
        path = self.write_task(task)
        ready = self.root / "lock-ready"
        release = self.root / "lock-release"
        fixture = Path(__file__).with_name("subprocess_fixture.py")
        holder = subprocess.Popen(
            [
                sys.executable,
                str(fixture),
                "hold-lock",
                str(self.workspace),
                str(ready),
                str(release),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.wait_for_path(ready, holder)
            completed = subprocess.run(
                [sys.executable, str(Path(runner.__file__).resolve()), str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        finally:
            release.write_text("release\n", encoding="utf-8")
            holder_stdout, holder_stderr = holder.communicate(timeout=5)
        self.assertEqual(holder.returncode, 0, f"{holder_stdout=} {holder_stderr=}")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = yaml.safe_load(Path(completed.stdout.strip()).read_text())
        self.assertEqual(result["execution"]["status"], "worktree_locked")

    def test_write_lock_contention_never_starts_sdk(self) -> None:
        task = self.task_value()
        task["permissions"].update(  # type: ignore[union-attr]
            {"sandbox_mode": "workspace_write", "network_access": False}
        )
        path = self.write_task(task)
        held = runner.WorktreeLock(str(self.workspace))
        self.assertTrue(held.acquire())
        try:
            factory = Factory([])
            invocation = runner.run_invocation(str(path), sdk_factory=factory)
        finally:
            held.release()
        result = yaml.safe_load(invocation.path.read_text())
        self.assertEqual(invocation.status, "worktree_locked")
        self.assertEqual(factory.instances, [])
        self.assertFalse((self.workspace / "run.yaml").exists())

    def test_read_only_does_not_acquire_lock(self) -> None:
        path = self.write_task()
        factory = Factory([{"events": [message_event(worker_output()), completed_event()]}])
        with mock.patch.object(runner.WorktreeLock, "acquire", side_effect=AssertionError("lock")):
            invocation = runner.run_invocation(str(path), sdk_factory=factory)
        self.assertEqual(invocation.status, "completed")

    def test_cli_invalid_task_prints_only_absolute_result_path(self) -> None:
        path = self.write_task({"kind": "wrong"})
        completed = subprocess.run(
            [sys.executable, str(Path(runner.__file__).resolve()), str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        stdout_lines = completed.stdout.splitlines()
        self.assertEqual(len(stdout_lines), 1)
        result_path = Path(stdout_lines[0])
        self.assertTrue(result_path.is_absolute())
        self.assertEqual(yaml.safe_load(result_path.read_text())["execution"]["status"], "invalid_task")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
