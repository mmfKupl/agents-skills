from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_chat
import run_manifest

# Each fake records how it was called, then prints what the real application prints.
FAKE_CLAUDE = """#!{python}
import json, os, sys, time
log = os.environ["FAKE_LOG"]
prompt = sys.stdin.read()
with open(log, "a") as handle:
    handle.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}}) + "\\n")
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "slow":
    time.sleep(30)
if mode == "crash":
    sys.stderr.write("boom: no credentials\\n")
    sys.exit(3)
print(json.dumps({{
    "type": "result", "subtype": "error_during_execution" if mode == "error" else "success",
    "is_error": mode == "error", "result": "it broke" if mode == "error" else "answer to: " + prompt,
    "session_id": "claude-session-1", "total_cost_usd": 0.25,
    "usage": {{"input_tokens": 10, "cache_read_input_tokens": 600, "cache_creation_input_tokens": 90,
              "output_tokens": 40}},
}}))
"""
FAKE_CODEX = """#!{python}
import json, os, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as handle:
    handle.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}}) + "\\n")
events = [
    {{"type": "thread.started", "thread_id": "codex-thread-1"}},
    {{"type": "turn.started"}},
    {{"type": "item.completed", "item": {{"type": "agent_message", "text": "thinking aloud"}}}},
    {{"type": "item.completed", "item": {{"type": "agent_message", "text": "answer to: " + prompt}}}},
    {{"type": "turn.completed", "usage": {{"input_tokens": 700, "cached_input_tokens": 500,
                                          "cache_write_input_tokens": 0, "output_tokens": 30,
                                          "reasoning_output_tokens": 5}}}},
]
if os.environ.get("FAKE_MODE") == "error":
    events = events[:2] + [{{"type": "turn.failed", "error": {{"message": "usage limit reached"}}}}]
print("not json noise")
for event in events:
    print(json.dumps(event))
"""


class RunChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "repo"
        self.workspace.mkdir()
        self.run_dir = self.root / "chat"
        self.log = self.root / "calls.jsonl"
        binaries = {}
        for name, text in (("claude", FAKE_CLAUDE), ("codex", FAKE_CODEX)):
            binaries[name] = self.root / f"fake-{name}"
            binaries[name].write_text(text.format(python=sys.executable))
            binaries[name].chmod(0o755)
        environment = patch.dict(os.environ, {
            "AGENT_RUNNER_CLAUDE_BIN": str(binaries["claude"]),
            "AGENT_RUNNER_CODEX_BIN": str(binaries["codex"]),
            "FAKE_LOG": str(self.log), "FAKE_MODE": "ok",
        })
        environment.start()
        self.addCleanup(environment.stop)

    def prompt(self, text: str, name: str = "prompt.md") -> str:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def start(self, **kwargs: object) -> tuple[int, dict]:
        values = {"workspace": str(self.workspace), "model": "opus", "effort": "high",
                  "prompt_file": self.prompt("/review-task UIB-1"), "run_dir": str(self.run_dir)}
        values.update(kwargs)
        code, output = run_chat.start(**values)
        return code, yaml.safe_load(output)

    def test_route_follows_the_model_name_unless_a_vendor_is_given(self) -> None:
        self.assertEqual(run_chat.chat_route("opus", "auto"), ("claude", "claude-opus-5-5"))
        self.assertEqual(run_chat.chat_route("Sol", "auto"), ("codex", "gpt-6.2-sol"))
        self.assertEqual(run_chat.chat_route("claude-haiku-5-5", "auto"), ("claude", "claude-haiku-5-5"))
        self.assertEqual(run_chat.chat_route("opus", "codex"), ("codex", "gpt-6.2-sol"))
        self.assertEqual(run_chat.chat_route("terra", "claude"), ("claude", "claude-sonnet-5-5"))

    def test_claude_chat_starts_records_and_continues(self) -> None:
        code, summary = self.start(name="W review: UIB-1", worktree="uib-1-review")
        self.assertEqual(code, 0)
        self.assertEqual((summary["vendor"], summary["model"], summary["status"], summary["turn"]),
                         ("claude", "claude-opus-5-5", "completed", 1))
        self.assertEqual(summary["session"], "claude-session-1")
        self.assertEqual(summary["report"], "answer to: /review-task UIB-1")
        self.assertEqual(summary["usage"], {"input_tokens": 700, "cached_input_tokens": 600,
                                            "cache_write_input_tokens": 90, "output_tokens": 40})
        self.assertEqual(summary["cost_usd"], 0.25)
        first = self.calls()[0]
        self.assertEqual(first["argv"], [
            "-p", "--worktree", "uib-1-review", "--name", "W review: UIB-1",
            "--output-format", "json", "--model", "claude-opus-5-5", "--effort", "high",
        ])
        self.assertEqual((first["cwd"], first["prompt"]), (str(self.workspace), "/review-task UIB-1"))
        self.assertEqual(Path(summary["result"]).read_text(), "answer to: /review-task UIB-1")

        code, output = run_chat.resume(run_dir=str(self.run_dir), prompt_file=self.prompt("option A", "answer.md"))
        summary = yaml.safe_load(output)
        self.assertEqual((code, summary["turn"], summary["report"]), (0, 2, "answer to: option A"))
        second = self.calls()[1]
        self.assertEqual(second["argv"], [
            "-p", "--resume", "claude-session-1", "--output-format", "json",
            "--model", "claude-opus-5-5", "--effort", "high",
        ])
        # The fake made no working copy, so the next turn stays in the repository folder.
        self.assertEqual(second["cwd"], str(self.workspace))
        record = yaml.safe_load((self.run_dir / "chat.yaml").read_text())
        self.assertEqual(record["cwd"], str(self.workspace))
        self.assertEqual([turn["status"] for turn in record["turns"]], ["completed", "completed"])
        self.assertEqual(record["status"], "completed")

    def test_later_claude_turns_run_in_the_working_copy(self) -> None:
        copy = self.workspace / ".claude" / "worktrees" / "uib-1-review"
        copy.mkdir(parents=True)
        self.start(worktree="uib-1-review")
        run_chat.resume(run_dir=str(self.run_dir), prompt_file=self.prompt("go on", "answer.md"))
        self.assertEqual(self.calls()[1]["cwd"], str(copy))

    def test_codex_chat_starts_and_continues(self) -> None:
        code, summary = self.start(model="Sol", worktree="any", unrestricted=True)
        self.assertEqual(code, 0)
        self.assertEqual((summary["vendor"], summary["model"], summary["session"]),
                         ("codex", "gpt-6.2-sol", "codex-thread-1"))
        self.assertEqual(summary["report"], "answer to: /review-task UIB-1")
        self.assertEqual(summary["usage"], {"input_tokens": 700, "cached_input_tokens": 500,
                                            "cache_write_input_tokens": 0, "output_tokens": 30})
        self.assertIsNone(summary["cost_usd"])
        self.assertEqual(self.calls()[0]["argv"], [
            "exec", "--json", "--skip-git-repo-check", "-m", "gpt-6.2-sol", "-c",
            'model_reasoning_effort="high"', "-C", str(self.workspace), "--worktree",
            "--dangerously-bypass-approvals-and-sandbox", "-",
        ])
        code, _ = run_chat.resume(run_dir=str(self.run_dir), prompt_file=self.prompt("go on", "answer.md"))
        self.assertEqual(code, 0)
        self.assertEqual(self.calls()[1]["argv"], [
            "exec", "resume", "codex-thread-1", "--json", "--skip-git-repo-check", "-m", "gpt-6.2-sol",
            "-c", 'model_reasoning_effort="high"', "--dangerously-bypass-approvals-and-sandbox", "-",
        ])
        self.assertEqual(self.calls()[1]["cwd"], str(self.workspace))

    def test_later_codex_turns_run_in_the_working_copy_codex_made(self) -> None:
        copy = self.root / "codex-home" / "worktrees" / "38e5" / "repo"
        copy.mkdir(parents=True)
        known = {str(self.workspace)}
        with patch("run_chat._worktree_paths", side_effect=[known, known | {str(copy)}]):
            self.start(model="Sol", worktree="any")
        record = yaml.safe_load((self.run_dir / "chat.yaml").read_text())
        self.assertEqual(record["cwd"], str(copy))
        run_chat.resume(run_dir=str(self.run_dir), prompt_file=self.prompt("go on", "answer.md"))
        self.assertEqual(self.calls()[1]["cwd"], str(copy))

        # Two working copies appeared at once, so there is no telling which one is the chat's.
        other = self.root / "chat-two"
        with patch("run_chat._worktree_paths", side_effect=[known, known | {str(copy), str(self.root)}]):
            self.start(model="Sol", worktree="any", run_dir=str(other))
        self.assertEqual(yaml.safe_load((other / "chat.yaml").read_text())["cwd"], str(self.workspace))

    def test_worktree_paths_lists_the_repository_copies(self) -> None:
        self.assertEqual(run_chat._worktree_paths(str(self.workspace)), set())
        import subprocess
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        self.assertEqual(run_chat._worktree_paths(str(self.workspace)), {str(self.workspace)})

    def test_unrestricted_claude_chat_skips_approvals(self) -> None:
        self.start(unrestricted=True)
        self.assertEqual(self.calls()[0]["argv"][-2:], ["--permission-mode", "bypassPermissions"])

    def test_failures_are_recorded_and_return_one(self) -> None:
        with patch.dict(os.environ, {"FAKE_MODE": "error"}):
            code, summary = self.start()
        self.assertEqual((code, summary["status"]), (1, "failed"))
        self.assertIn("error_during_execution: it broke", summary["error"])
        self.assertEqual(summary["session"], "claude-session-1")

        other = self.root / "chat-crash"
        with patch.dict(os.environ, {"FAKE_MODE": "crash"}):
            code, summary = self.start(run_dir=str(other))
        self.assertEqual((code, summary["status"], summary["session"]), (1, "failed", None))
        self.assertIn("printed no result", summary["error"])
        with self.assertRaisesRegex(run_manifest.ManifestError, "no session to continue"):
            run_chat.resume(run_dir=str(other), prompt_file=self.prompt("again", "answer.md"))

        codex = self.root / "chat-codex"
        with patch.dict(os.environ, {"FAKE_MODE": "error"}):
            code, summary = self.start(model="gpt-6.2-sol", run_dir=str(codex))
        self.assertEqual((code, summary["status"], summary["error"]), (1, "failed", "usage limit reached"))

    def test_a_turn_that_runs_too_long_is_stopped(self) -> None:
        with patch.dict(os.environ, {"FAKE_MODE": "slow"}):
            code, summary = self.start(timeout_minutes=0.02)
        self.assertEqual((code, summary["status"]), (1, "timed_out"))
        self.assertIn("stopped after", summary["error"])
        record = yaml.safe_load((self.run_dir / "chat.yaml").read_text())
        self.assertEqual(record["status"], "timed_out")

    def test_bad_input_is_refused_before_anything_starts(self) -> None:
        with self.assertRaisesRegex(run_manifest.ManifestError, "unsupported effort"):
            self.start(effort="max")
        with self.assertRaisesRegex(run_manifest.ManifestError, "not a folder"):
            self.start(workspace=str(self.root / "missing"))
        with self.assertRaisesRegex(run_manifest.ManifestError, "prompt is empty"):
            self.start(prompt_file=self.prompt("  \n", "empty.md"))
        self.assertFalse(self.log.exists())
        self.start()
        with self.assertRaisesRegex(run_manifest.ManifestError, "already holds a chat"):
            self.start()
        with patch.dict(os.environ, {"AGENT_RUNNER_CLAUDE_BIN": "", "PATH": str(self.root)}):
            with self.assertRaisesRegex(run_manifest.ManifestError, "cannot find `claude`"):
                self.start(run_dir=str(self.root / "chat-no-binary"))

    def test_the_command_line_starts_and_continues_a_chat(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run_manifest.main([
                "chat", "--workspace", str(self.workspace), "--model", "haiku", "--effort", "low",
                "--prompt-file", self.prompt("hello"), "--run-dir", str(self.run_dir),
            ])
        summary = yaml.safe_load(stdout.getvalue())
        self.assertEqual((code, summary["model"], summary["status"]), (0, "claude-haiku-5-5", "completed"))
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run_manifest.main(["chat-resume", str(self.run_dir), "--prompt-file", self.prompt("more", "a.md")])
        self.assertEqual((code, yaml.safe_load(stdout.getvalue())["turn"]), (0, 2))
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            code = run_manifest.main(["chat-resume", str(self.root / "nowhere"), "--prompt-file", self.prompt("x", "b.md")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
