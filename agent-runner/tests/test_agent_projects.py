from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_projects


class AgentProjectsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / "agent-projects"
        self.use_chat("chat-one")

    def use_chat(self, chat_id: str, variable: str = "CLAUDE_CODE_SESSION_ID") -> None:
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
        # No Linear key here, so no command reaches for the network.
        environment.update({agent_projects.HOME_VARIABLE: str(self.home), variable: chat_id,
                            "AGENT_PROJECTS_LINEAR_KEY_FILE": str(self.home.parent / "no-linear-key")})
        patcher = patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_command(self, *argv: str, stdin: str = "") -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), patch.object(sys, "stdin", io.StringIO(stdin)):
            code = agent_projects.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def ok(self, *argv: str, stdin: str = "") -> dict:
        code, stdout, stderr = self.run_command(*argv, stdin=stdin)
        self.assertEqual(code, 0, stderr)
        return yaml.safe_load(stdout)

    def create_project(self, name: str = "billing") -> dict:
        self.ok("init")
        return self.ok("project", "create", name, "--repository", "/repo", "--tracker", "linear",
                       "--scope", "linear_project=Billing")

    def ticket_file(self, ticket: str = "UIB-123") -> Path:
        return self.home / "tickets" / f"{ticket}.md"

    def test_init_creates_the_folder_once(self) -> None:
        first = self.ok("init")
        self.assertEqual(first, {"home": str(self.home), "created": True, "projects": [],
                                 "linear": f"no key: {self.home.parent / 'no-linear-key'}", "watching": "not running"})
        self.assertTrue((self.home / "tickets").is_dir())
        self.assertTrue((self.home / "triggers").is_dir())
        self.assertFalse(self.ok("init")["created"])

    def test_project_create_show_and_list(self) -> None:
        created = self.create_project()
        self.assertEqual(created["scope"], {"linear_project": "Billing"})
        self.assertEqual(created["folder"], str(self.home / "project-billing"))
        self.assertTrue((self.home / "project-billing" / "reports").is_dir())
        self.assertEqual(self.ok("project", "show", "billing")["tracker"], "linear")
        self.assertEqual(self.ok("project", "list"), {"projects": ["billing"]})

    def test_project_create_refuses_a_bad_name_a_duplicate_and_a_missing_folder(self) -> None:
        code, _, stderr = self.run_command("project", "create", "billing", "--repository", "/repo")
        self.assertEqual(code, 2)
        self.assertIn("agent-projects init", stderr)
        self.create_project()
        self.assertEqual(self.run_command("project", "create", "billing", "--repository", "/repo")[0], 2)
        self.assertEqual(self.run_command("project", "create", "../x", "--repository", "/repo")[0], 2)
        self.assertEqual(self.run_command("project", "create", "ok", "--repository", "/repo", "--scope", "x")[0], 2)

    def test_project_with_named_tickets(self) -> None:
        self.ok("init")
        created = self.ok("project", "create", "few", "--repository", "/repo", "--ticket", "uib-1", "--ticket", "UIB-2")
        self.assertEqual(created["scope"], {"tickets": ["UIB-1", "UIB-2"]})

    def test_project_chat_records_the_calling_chat(self) -> None:
        self.create_project()
        result = self.ok("project", "chat", "billing", "--title", "R project: Billing")
        self.assertEqual(result["chat"]["id"], "chat-one")
        self.assertEqual(result["chat"]["host"], "claude")
        self.assertEqual(self.ok("project", "show", "billing")["chat"]["title"], "R project: Billing")

    def test_record_commands_do_nothing_without_the_folder(self) -> None:
        for argv in (
            ("ticket", "take", "UIB-1", "--workflow", "review"),
            ("ticket", "release", "UIB-1"),
            ("ticket", "note", "UIB-1", "decided"),
        ):
            code, stdout, _ = self.run_command(*argv)
            self.assertEqual((code, stdout.strip()), (0, agent_projects.SKIPPED))
        self.assertFalse(self.home.exists())

    def test_take_and_release_by_one_chat(self) -> None:
        self.create_project()
        taken = self.ok("ticket", "take", "uib-123", "--workflow", "review", "--project", "billing",
                        "--title", "W review: UIB-123 Limits", "--cwd", "/work")
        self.assertEqual(taken["ticket"], "UIB-123")
        self.assertEqual(taken["also_taken_by"], [])
        status = self.ok("status", "--project", "billing")
        self.assertEqual(len(status["tickets"]), 1)
        holder = status["tickets"][0]["taken"][0]
        self.assertEqual((holder["title"], holder["workflow"], holder["host"]),
                         ("W review: UIB-123 Limits", "review", "claude"))
        self.assertIn('taken for review by "W review: UIB-123 Limits" (claude)', status["tickets"][0]["last_event"])

        released = self.ok("ticket", "release", "UIB-123", "--result", "ready after fixes, 2 findings",
                           "--pr", "https://example.test/pr/1")
        self.assertTrue(released["released"])
        after = self.ok("status")["tickets"][0]
        self.assertEqual(after["taken"], [])
        self.assertEqual(after["pr"], "https://example.test/pr/1")
        self.assertIn("released by", after["last_event"])
        self.assertIn("ready after fixes, 2 findings", after["last_event"])
        self.assertFalse(self.ok("ticket", "release", "UIB-123")["released"])

    def test_take_again_by_the_same_chat_keeps_one_record(self) -> None:
        self.create_project()
        self.ok("ticket", "take", "UIB-123", "--workflow", "review", "--project", "billing")
        self.ok("ticket", "take", "UIB-123", "--workflow", "review", "--title", "W review: UIB-123")
        text = self.ticket_file().read_text(encoding="utf-8")
        self.assertEqual(text.count("taken for review"), 1)
        status = self.ok("status")["tickets"][0]
        self.assertEqual(len(status["taken"]), 1)
        self.assertEqual(status["projects"], ["billing"])
        self.assertEqual(status["taken"][0]["title"], "W review: UIB-123")

    def test_second_chat_sees_the_first_holder(self) -> None:
        self.ok("init")
        self.ok("ticket", "take", "UIB-123", "--workflow", "develop", "--title", "W develop: UIB-123")
        self.use_chat("thread-two", variable="CODEX_THREAD_ID")
        second = self.ok("ticket", "take", "UIB-123", "--workflow", "review")
        self.assertEqual([(other["title"], other["host"], other["workflow"]) for other in second["also_taken_by"]],
                         [("W develop: UIB-123", "claude", "develop")])
        self.ok("ticket", "release", "UIB-123")
        remaining = self.ok("status")["tickets"][0]["taken"]
        self.assertEqual([entry["id"] for entry in remaining], ["chat-one"])
        self.assertTrue(self.ok("ticket", "release", "UIB-123", "--chat", "chat-one")["released"])

    def test_take_refuses_an_unknown_project_and_a_bad_ticket(self) -> None:
        self.ok("init")
        self.assertEqual(self.run_command("ticket", "take", "UIB-1", "--workflow", "review", "--project", "nope")[0], 2)
        self.assertEqual(self.run_command("ticket", "take", "../UIB-1", "--workflow", "review")[0], 2)
        self.assertEqual(list((self.home / "tickets").glob("*.md")), [])

    def test_note_and_show_keep_hand_written_history(self) -> None:
        self.ok("init")
        self.ok("ticket", "note", "UIB-123", "decided:", "keep", "the old endpoint")
        path = self.ticket_file()
        path.write_text(path.read_text(encoding="utf-8") + "\nA line the developer wrote by hand.\n", encoding="utf-8")
        self.ok("ticket", "note", "UIB-123", "second note")
        code, stdout, _ = self.run_command("ticket", "show", "UIB-123")
        self.assertEqual(code, 0)
        self.assertIn(f"file: {path}", stdout)
        self.assertIn("decided: keep the old endpoint", stdout)
        self.assertIn("A line the developer wrote by hand.", stdout)
        self.assertLess(stdout.index("developer wrote by hand"), stdout.index("second note"))
        self.assertEqual(self.ok("ticket", "show", "UIB-999")["history"], "none")

    def test_report_add_files_the_report_and_links_the_ticket(self) -> None:
        self.create_project()
        first = self.ok("report", "add", "--project", "billing", "--ticket", "uib-123", "--kind", "review",
                        stdin="### Verdict\nready")
        report = Path(first["report"])
        self.assertEqual(report.parent, self.home / "project-billing" / "reports")
        self.assertRegex(report.name, r"^\d{4}-\d{2}-\d{2}-UIB-123-review\.md$")
        self.assertEqual(report.read_text(encoding="utf-8"), "### Verdict\nready\n")
        source = self.home / "draft.md"
        source.write_text("second\n", encoding="utf-8")
        second = self.ok("report", "add", "--project", "billing", "--ticket", "UIB-123", "--kind", "review",
                         "--file", str(source))
        self.assertTrue(second["report"].endswith("-UIB-123-review-2.md"))
        status = self.ok("status", "--project", "billing")["tickets"][0]
        self.assertEqual(status["last_report"], second["report"])
        self.assertIn("review report:", status["last_event"])

    def test_report_add_refuses_an_empty_report_and_an_unknown_project(self) -> None:
        self.create_project()
        self.assertEqual(self.run_command("report", "add", "--project", "billing", "--ticket", "UIB-1",
                                          "--kind", "review", stdin="  \n")[0], 2)
        self.assertEqual(self.run_command("report", "add", "--project", "nope", "--ticket", "UIB-1",
                                          "--kind", "review", stdin="text")[0], 2)

    def test_status_filters_by_project(self) -> None:
        self.create_project()
        self.ok("ticket", "take", "UIB-1", "--workflow", "review", "--project", "billing")
        self.ok("ticket", "take", "UIB-2", "--workflow", "draft")
        self.assertEqual([item["ticket"] for item in self.ok("status", "--project", "billing")["tickets"]], ["UIB-1"])
        everything = self.ok("status")
        self.assertEqual([item["ticket"] for item in everything["tickets"]], ["UIB-1", "UIB-2"])
        self.assertEqual(everything["projects"], ["billing"])
        self.assertEqual(self.run_command("status", "--project", "nope")[0], 2)

    def test_a_broken_ticket_file_is_reported(self) -> None:
        self.ok("init")
        self.ticket_file().write_text("no front matter\n", encoding="utf-8")
        code, _, stderr = self.run_command("ticket", "note", "UIB-123", "text")
        self.assertEqual(code, 2)
        self.assertIn("front matter", stderr)


if __name__ == "__main__":
    unittest.main()
