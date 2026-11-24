from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_projects
import project_watch
from test_run_chat import FAKE_CLAUDE

READY_TRIGGERS = Path(__file__).resolve().parents[2] / "skills" / "project-master" / "triggers"
# The loop reads the real clock, so the tickets are dated from it.
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def issue(identifier: str, *, status: str = "In Review", assignee: str | None = "me", actor: str | None = "other",
          minutes_ago: float = 600, moved_to: str | None = None, move_id: str | None = None) -> dict:
    """A ticket as Linear returns it, with one move into its status and one later edit."""
    moved = (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "identifier": identifier, "title": f"Title of {identifier}", "url": f"https://linear.app/x/{identifier}",
        "description": f"Description of {identifier}", "state": {"name": status},
        "assignee": {"id": assignee, "name": assignee} if assignee else None,
        "history": {"nodes": [
            {"id": f"{identifier}-edit", "createdAt": NOW.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
             "actor": {"id": "other", "name": "Other"}, "botActor": None, "fromState": None, "toState": None},
            {"id": move_id or f"{identifier}-move", "createdAt": moved,
             "actor": {"id": actor, "name": actor.title()} if actor else None, "botActor": None,
             "fromState": {"name": "In Progress"}, "toState": {"name": moved_to or status}},
        ]},
    }


def at(minutes: float) -> str:
    return (NOW + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def comment(identity: str, minutes: float, body: str, user: str | None = "other") -> dict:
    return {"id": identity, "createdAt": at(minutes), "url": f"https://linear.app/x#{identity}", "body": body,
            "user": {"id": user, "name": user.title()} if user else None, "botActor": None if user else {"name": "CI"}}


def commented(identifier: str, comments: list[dict], *, pull: str | None = None, state_type: str = "started",
              project: str = "Billing") -> dict:
    """A ticket as the comments query returns it."""
    return {
        "identifier": identifier, "title": f"Title of {identifier}", "url": f"https://linear.app/x/{identifier}",
        "description": f"Description of {identifier}", "state": {"name": "In Review", "type": state_type},
        "project": {"name": project}, "attachments": {"nodes": [{"url": pull}] if pull else []},
        "history": {"nodes": [{"createdAt": at(-600), "actor": {"name": "Other"}, "botActor": None,
                               "fromState": {"name": "In Progress"}, "toState": {"name": "In Review"}}]},
        "comments": {"nodes": comments},
    }


class FakeCheck:
    """Stands in for the check job: it writes the summary the job would print."""

    def __init__(self, outcome: str) -> None:
        self.outcome, self.commands = outcome, []

    def __call__(self, command: list[str], **options) -> SimpleNamespace:
        self.commands.append(command)
        options["stdout"].write(yaml.safe_dump({"check_outcome": self.outcome}).encode())
        return SimpleNamespace(pid=990_000 + len(self.commands), poll=lambda: 0)


class ProjectWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "agent-projects"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.key = self.root / "linear-api-key"
        self.key.write_text("lin_api_test\n")
        self.log = self.root / "calls.jsonl"
        fake = self.root / "fake-claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable))
        fake.chmod(0o755)
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "FAKE_MODE")}
        environment.update({
            agent_projects.HOME_VARIABLE: str(self.home), "CLAUDE_CODE_SESSION_ID": "project-chat",
            project_watch.KEY_VARIABLE: str(self.key), project_watch.TRIGGERS_VARIABLE: str(READY_TRIGGERS),
            "AGENT_RUNNER_CLAUDE_BIN": str(fake), "FAKE_LOG": str(self.log),
        })
        patcher = patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.issues: list[dict] = []
        self.closed: set[str] = set()
        self.commented: list[dict] = []
        self.comment_queries: list[list[int]] = []
        self.queries: list[dict] = []
        patcher = patch.object(project_watch, "linear", self.fake_linear)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.wait_for_runs)

    def fake_linear(self, query: str, variables: dict | None = None, timeout: float = 30) -> dict:
        if "viewer" in query:
            return {"viewer": {"id": "me", "name": "Ivan"}}
        if "comments(" in query:
            numbers = variables["filter"]["number"]["in"]
            self.comment_queries.append(numbers)
            nodes = [item for item in self.commented if int(item["identifier"].split("-")[1]) in numbers]
            return {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}
        if "history" not in query:
            numbers = variables["filter"]["number"]["in"]
            return {"issues": {"nodes": [
                {"identifier": f"UIB-{number}", "state": {"type": "completed" if f"UIB-{number}" in self.closed else "started"}}
                for number in numbers]}}
        self.queries.append(variables or {})
        statuses = variables["filter"]["state"]["name"]["in"]
        nodes = [item for item in self.issues if item["state"]["name"] in statuses]
        return {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}

    def wait_for_runs(self) -> None:
        for child in list(project_watch._children.values()):
            child.wait(timeout=30)
        project_watch._children.clear()

    def command(self, *argv: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = agent_projects.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def ok(self, *argv: str) -> dict:
        code, stdout, stderr = self.command(*argv)
        self.assertEqual(code, 0, stderr)
        return yaml.safe_load(stdout)

    def project(self, name: str = "billing", *, watched: bool = True) -> None:
        self.ok("init")
        self.ok("project", "create", name, "--repository", str(self.repo), "--tracker", "linear",
                "--scope", "linear_project=Billing")
        self.ok("project", "chat", name, "--title", "project: Billing")
        if watched:
            self.ok("project", "triggers", name, "--on", "my review")

    def watched_project(self) -> None:
        """A project whose first poll is over, so that new matches start by themselves."""
        self.project()
        project_watch.poll(NOW)

    def reviewed(self, ticket: str) -> None:
        """A review of the ticket is on record on this machine, in the project."""
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": f"review-{ticket}"}):
            self.ok("ticket", "take", ticket, "--workflow", "review", "--project", "billing")
            with patch.object(sys, "stdin", io.StringIO("review report text")):
                self.ok("report", "add", "--project", "billing", "--ticket", ticket, "--kind", "review")
            self.ok("ticket", "release", ticket)

    def run_check(self, outcome: str) -> tuple[FakeCheck, list[str]]:
        """Two rounds of the loop: the first starts the check, the second reads its answer."""
        check = FakeCheck(outcome)
        with patch.object(project_watch.subprocess, "Popen", check):
            project_watch.cycle(read_tracker=False)
            lines = project_watch.cycle(read_tracker=False)
        return check, lines

    def by_id(self) -> dict[int, dict]:
        return {event["id"]: event for event in project_watch.events(None, True)["events"]}

    def states(self) -> dict[str, str]:
        return {event["ticket"]: event["state"] for event in project_watch.events(None, True)["events"]}

    def write_trigger(self, folder: Path, text: str, name: str = "broken.yaml") -> None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)
        os.environ[project_watch.TRIGGERS_VARIABLE] = str(folder)

    def test_ready_trigger_loads(self) -> None:
        triggers, problems = project_watch.load_triggers()

        self.assertEqual(problems, [])
        self.assertEqual(triggers["my review"]["run"]["review"]["command"], "/review-task {ticket}")
        self.assertEqual(triggers["my progress"]["check"]["model"], "haiku")
        self.assertEqual([row["name"] for row in self.ok("trigger", "list")["triggers"]], ["my progress", "my review"])

    def test_trigger_the_script_does_not_understand_is_refused(self) -> None:
        good = (READY_TRIGGERS / "my-review.yaml").read_text()
        cases = {
            "unknown field `assigne`": good.replace("assignee:", "assigne:"),
            "an entry must be": good.replace("event: status_changed", "event: renamed"),
            "a comment_added entry needs `ticket`": good.replace(
                "    ticket: reviewed_in_current_env     # a review of it is on record here\n", ""),
            "an entry with no `then` needs a `check`": good[:good.index("check:")] + good[good.index("run:"):],
            "`check` must hold": good.replace("  effort: low\n  prompt: |\n    Read the comment", "  prompt: |\n    Read the comment"),
            "`skip` of a comment_added entry": good.replace("skip: agent_comment", "skip: ticket_taken_in_current_env", 1),
            "`then` must name": good.replace("then: review", "then: revew"),
            "unknown model": good.replace("model: opus", "model: gpt-9"),
            "`effort` must be": good.replace("effort: high", "effort: huge"),
            "`assignee` must be": good.replace("assignee: current_user", "assignee: me"),
            "unknown field `filter`": good + "filter: all\n",
        }
        for expected, text in cases.items():
            with self.subTest(expected):
                self.write_trigger(self.root / "triggers", text)
                triggers, problems = project_watch.load_triggers()
                self.assertEqual(triggers, {})
                self.assertIn(expected, problems[0])

    def test_trigger_saved_on_the_machine_wins_over_the_ready_one(self) -> None:
        mine = self.root / "mine"
        self.write_trigger(mine, (READY_TRIGGERS / "my-review.yaml").read_text().replace("model: opus", "model: sonnet"))
        os.environ[project_watch.TRIGGERS_VARIABLE] = os.pathsep.join((str(mine), str(READY_TRIGGERS)))

        triggers, _ = project_watch.load_triggers()

        self.assertEqual(triggers["my review"]["run"]["review"]["model"], "sonnet")

    def test_first_poll_holds_and_later_moves_wait_to_start(self) -> None:
        self.project()
        self.issues = [issue("UIB-1")]

        first = project_watch.poll(NOW)

        self.assertEqual([(event["ticket"], event["state"]) for event in first["new"]], [("UIB-1", "held")])
        moved = (NOW - timedelta(minutes=600)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(first["new"][0]["what"], f"moved from In Progress to In Review by Other at {moved}")
        self.assertNotIn("key", first["new"][0])

        self.issues += [issue("UIB-2", minutes_ago=10), issue("UIB-3", minutes_ago=0.5)]
        second = project_watch.poll(NOW)

        # UIB-1 is known, and UIB-3 moved too recently to act on.
        self.assertEqual([(event["ticket"], event["state"]) for event in second["new"]], [("UIB-2", "waiting")])
        self.assertEqual([event["ticket"] for event in second["held"]], ["UIB-1"])

        third = project_watch.poll(NOW + timedelta(minutes=5))
        self.assertEqual([(event["ticket"], event["state"]) for event in third["new"]], [("UIB-3", "waiting")])
        self.assertEqual(project_watch.poll(NOW + timedelta(minutes=6))["new"], [])

    def test_a_ticket_that_comes_back_to_the_status_counts_again(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        project_watch.poll(NOW)
        self.issues = [issue("UIB-1", minutes_ago=5, move_id="second-move")]

        again = project_watch.poll(NOW)

        self.assertEqual([event["ticket"] for event in again["new"]], ["UIB-1"])
        self.assertEqual(len(project_watch.events(None, True)["events"]), 2)

    def test_poll_ignores_what_does_not_fit_the_trigger(self) -> None:
        self.watched_project()
        self.issues = [
            issue("UIB-1", actor="me"),                      # the current user moved it
            issue("UIB-2", assignee="other"),                # someone else reviews it
            issue("UIB-3", assignee=None),
            issue("UIB-4", moved_to="In Progress"),          # the move into In Review is not in the history page
            issue("UIB-5", status="In Progress"),
        ]

        self.assertEqual(project_watch.poll(NOW)["new"], [])

    def test_move_by_an_integration_counts_as_not_the_current_user(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", actor=None)]

        event = project_watch.poll(NOW)["new"][0]

        self.assertEqual(event["state"], "waiting")
        self.assertIn("by an integration", event["what"])

    def test_ticket_a_chat_already_works_on_is_skipped(self) -> None:
        self.watched_project()
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "review-chat"}):
            self.ok("ticket", "take", "UIB-1", "--workflow", "review", "--title", "W review: UIB-1 Limits")
        self.issues = [issue("UIB-1")]

        event = project_watch.poll(NOW)["new"][0]

        self.assertEqual(event["state"], "skipped")
        self.assertIn("W review: UIB-1 Limits", event["note"])
        self.assertEqual(project_watch.events(None, False)["events"], [])

    def test_poll_reports_a_missing_key_and_an_unknown_trigger(self) -> None:
        self.project()
        self.key.unlink()

        self.assertIn("the Linear key is missing", project_watch.poll(NOW)["problems"][0])

        document = self.home / "project-billing" / "project.yaml"
        document.write_text(document.read_text().replace("- my review", "- gone"))
        self.assertEqual(project_watch.poll(NOW)["problems"], ["project billing: no trigger named 'gone'"])
        self.assertEqual(project_watch.events(None, True)["problems"], ["project billing: no trigger named 'gone'"])

    def test_scope_becomes_linear_filters(self) -> None:
        self.ok("init")
        self.ok("project", "create", "pair", "--repository", str(self.repo), "--tracker", "linear",
                "--ticket", "UIB-7", "--ticket", "uib-9", "--ticket", "COM-3")
        self.ok("project", "triggers", "pair", "--on", "my review")

        project_watch.poll(NOW)

        self.assertEqual([query["filter"] for query in self.queries], [
            {"team": {"key": {"eq": "COM"}}, "number": {"in": [3]}, "state": {"name": {"in": ["In Review"]}}},
            {"team": {"key": {"eq": "UIB"}}, "number": {"in": [7, 9]}, "state": {"name": {"in": ["In Review"]}}},
        ])

    def test_every_page_of_tickets_is_read(self) -> None:
        pages = [
            {"issues": {"nodes": [issue("UIB-1")], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}},
            {"issues": {"nodes": [issue("UIB-2")], "pageInfo": {"hasNextPage": False, "endCursor": None}}},
        ]
        with patch.object(project_watch, "linear", side_effect=pages) as linear:
            found = project_watch._issues({"linear_project": "Billing"}, ["In Review"])

        self.assertEqual([item["identifier"] for item in found], ["UIB-1", "UIB-2"])
        self.assertEqual(linear.call_args_list[1].args[1]["after"], "next")

    def test_ticket_named_by_number_goes_to_the_project_that_names_it(self) -> None:
        self.watched_project()                                   # billing covers the whole Linear project
        self.ok("project", "create", "hotfix", "--repository", str(self.repo), "--tracker", "linear",
                "--ticket", "UIB-1")
        self.ok("project", "triggers", "hotfix", "--on", "my review")
        project_watch.poll(NOW)
        self.issues = [issue("UIB-1", minutes_ago=30), issue("UIB-2", minutes_ago=30)]

        found = project_watch.poll(NOW)["new"]

        self.assertEqual([(event["ticket"], event["project"]) for event in found],
                         [("UIB-2", "billing"), ("UIB-1", "hotfix")])

    def test_naming_a_ticket_claims_it_only_for_the_triggers_that_project_has(self) -> None:
        mine = self.root / "mine"
        self.write_trigger(mine, (READY_TRIGGERS / "my-review.yaml").read_text().replace("name: my review", "name: other"))
        os.environ[project_watch.TRIGGERS_VARIABLE] = os.pathsep.join((str(mine), str(READY_TRIGGERS)))
        self.watched_project()
        self.ok("project", "create", "hotfix", "--repository", str(self.repo), "--tracker", "linear",
                "--ticket", "UIB-1")
        self.ok("project", "triggers", "hotfix", "--on", "other")
        project_watch.poll(NOW)
        self.issues = [issue("UIB-1", minutes_ago=30)]

        found = project_watch.poll(NOW)["new"]

        self.assertEqual(sorted((event["project"], event["trigger"]) for event in found),
                         [("billing", "my review"), ("hotfix", "other")])

    def test_tracker_is_not_read_between_readings_but_waiting_events_start(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        project_watch.poll(NOW)
        self.queries.clear()

        lines = project_watch.cycle(read_tracker=False)

        self.assertEqual(self.queries, [])
        self.assertEqual(lines, ["UIB-1: review run started"])

    def run_with_working_copy(self) -> Path:
        """An ended run whose chat worked in a working copy of the repository."""
        def git(*arguments: str) -> None:
            subprocess.run(["git", "-C", str(self.repo), *arguments], check=True, capture_output=True)
        git("init", "-q")
        git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "start")
        copy = self.repo / ".claude" / "worktrees" / "uib-1-review-1"
        git("worktree", "add", "-q", "-b", "worktree-uib-1-review-1", str(copy))
        git("worktree", "lock", str(copy))
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        project_watch.poll(NOW)
        run_dir = self.home / "project-billing" / "runs" / "one"
        run_dir.mkdir(parents=True)
        (run_dir / "chat.yaml").write_text(yaml.safe_dump(
            {"workspace": str(self.repo), "cwd": str(copy), "worktree": "uib-1-review-1", "status": "completed"}))
        with project_watch._state() as state:
            state["events"][0].update(state="finished", run_dir=str(run_dir))
        return copy

    def test_working_copy_is_removed_once_the_ticket_is_closed(self) -> None:
        copy = self.run_with_working_copy()

        self.assertEqual(project_watch.cycle(), [])
        self.assertTrue(copy.is_dir())                       # the ticket is still open

        self.closed = {"UIB-1"}
        self.assertEqual(project_watch.cycle(), ["UIB-1: closed in the tracker, working copy removed"])

        self.assertFalse(copy.exists())
        branches = subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "worktree-*"],
                                  capture_output=True, text=True).stdout
        self.assertEqual(branches, "")
        self.assertIn("copy_removed", project_watch.events(None, True)["events"][0])
        self.assertEqual(project_watch.cycle(), [])

    def test_working_copy_with_changes_is_kept(self) -> None:
        copy = self.run_with_working_copy()
        (copy / "notes.txt").write_text("not committed")
        self.closed = {"UIB-1"}

        lines = project_watch.cycle()

        self.assertTrue(copy.is_dir())
        self.assertIn("UIB-1: working copy kept", lines[0])
        self.assertIn(str(copy), project_watch.events(None, True)["events"][0]["copy_kept"])
        self.assertEqual(project_watch.cycle(), [])

    def test_comment_on_a_reviewed_ticket_goes_through_the_check_to_a_run(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.commented = [commented("UIB-1", [
            comment("c-old", -60, "written before the trigger was on"),
            comment("c-agent", 5, "$develop-please:\n\n### Problem"),
            comment("c-bot", 5, "deployed", user=None),
            comment("c-new", 5, "Fixed both points, please look again"),
        ])]

        found = project_watch.poll(NOW + timedelta(minutes=10))["new"]

        self.assertEqual([(event["ticket"], event["state"], event["run"]) for event in found], [("UIB-1", "checking", None)])
        self.assertIn("commented on by Other at", found[0]["what"])
        packet = Path(found[0]["check_dir"], "packet.md").read_text()
        self.assertIn("Outcomes, answer with exactly one: own_review, author_answered, noise", packet)
        self.assertIn("<<<\nFixed both points, please look again\n>>>", packet)
        self.assertIn("Written from the current user's own account: no", packet)
        self.assertIn("review report text", packet)
        self.assertIn("In Progress -> In Review by Other", packet)
        self.assertEqual(project_watch.poll(NOW + timedelta(minutes=20))["new"], [])

        check, lines = self.run_check("author_answered")

        command = check.commands[0]
        self.assertEqual([command[command.index(flag) + 1] for flag in ("--role", "--model", "--effort", "--vendor")],
                         ["project-check", "haiku", "low", "claude"])
        self.assertEqual(lines, ["UIB-1: check picked author_answered, now waiting"])

        project_watch.cycle(read_tracker=False)
        self.wait_for_runs()
        call = json.loads(self.log.read_text().splitlines()[0])
        self.assertTrue(call["prompt"].startswith("/project-scope billing Report which review points the author closed"))
        self.assertIn("A check sorted this event as `author_answered`.", call["prompt"])
        self.assertEqual(call["argv"][call["argv"].index("--model") + 1], "claude-sonnet-5-5")

    def test_comments_of_one_reading_are_one_event_and_a_quiet_run_tells_nobody(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.commented = [commented("UIB-1", [comment("c2", 6, "and the test is missing", user="me"),
                                              comment("c1", 5, "I would rename this", user="me")])]

        found = project_watch.poll(NOW + timedelta(minutes=10))["new"]

        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["what"].endswith("#c2 (and 1 more before it)"))
        packet = Path(found[0]["check_dir"], "packet.md").read_text()
        self.assertIn("Comment 1 of 2", packet)
        self.assertIn("<<<\nI would rename this\n>>>", packet)
        self.assertIn("Written from the current user's own account: yes", packet)

        self.run_check("own_review")
        project_watch.cycle(read_tracker=False)
        self.wait_for_runs()
        with patch.object(sys, "stdin", io.StringIO("remarks recorded")):
            self.ok("report", "add", "--project", "billing", "--ticket", "UIB-1", "--kind", "note")
        with patch.object(project_watch, "_tell") as tell:
            project_watch.cycle(read_tracker=False)

        tell.assert_not_called()
        self.assertEqual(self.by_id()[1]["state"], "finished")
        self.assertIn("the project chat is not told", self.ok("trigger", "list")["triggers"][1]["starts"]["own_review"])

    def test_check_that_says_noise_or_nothing_usable_starts_no_run(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.commented = [commented("UIB-1", [comment("c1", 5, "thanks!")])]
        project_watch.poll(NOW + timedelta(minutes=10))

        self.run_check("noise")

        self.assertEqual((self.by_id()[1]["state"], self.by_id()[1]["note"]), ("skipped", "the check sorted it as noise"))
        self.assertIn("has nothing to start", self.command("watch", "start", "1")[2])

        self.commented[0]["comments"]["nodes"].append(comment("c2", 6, "what about the limit?"))
        project_watch.poll(NOW + timedelta(minutes=10))
        self.run_check("unclear")

        self.assertEqual(self.by_id()[2]["state"], "failed")
        self.assertIn("the check picked no outcome of the trigger (it answered 'unclear')", self.by_id()[2]["note"])
        self.assertEqual(self.ok("watch", "start", "2")["events"][0]["state"], "checking")

    def test_comment_that_came_in_during_a_pause_is_checked_and_then_held(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.ok("pause")
        self.commented = [commented("UIB-1", [comment("c1", 5, "I would rename this, and the test is missing")], )]

        self.assertEqual([event["state"] for event in self.ok("resume")["new"]], ["checking"])
        self.run_check("own_review")

        self.assertEqual(self.by_id()[1]["state"], "held")
        self.assertEqual(self.ok("watch", "start", "1")["events"][0]["state"], "waiting")

    def test_pull_request_reviews_are_read_and_bots_are_left_out(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.commented = [commented("UIB-1", [], pull="https://github.com/acme/app/pull/7")]
        answer = {"viewer": {"login": "ivan"}, "repository": {"pullRequest": {
            "reviews": {"nodes": [
                {"id": "r1", "state": "CHANGES_REQUESTED", "body": "", "submittedAt": at(5), "url": "https://github.com/acme/app/pull/7#r1",
                 "author": {"login": "adam", "__typename": "User"}, "comments": {"nodes": [{"body": "this leaks", "path": "src/a.ts"}]}},
                {"id": "r2", "state": "COMMENTED", "body": "Codex Review", "submittedAt": at(5), "url": "https://github.com/acme/app/pull/7#r2",
                 "author": {"login": "codex", "__typename": "Bot"}, "comments": {"nodes": []}},
            ]},
            "comments": {"nodes": [
                {"id": "i1", "body": "/e2e-preview projects/e2e", "createdAt": at(5), "url": "https://github.com/acme/app/pull/7#i1",
                 "author": {"login": "ivan", "__typename": "User"}},
            ]},
        }}}

        with patch.object(project_watch, "github", return_value=answer) as github:
            found = project_watch.poll(NOW + timedelta(minutes=10))["new"]

        self.assertEqual(github.call_args.kwargs, {"owner": "acme", "name": "app", "number": 7})
        self.assertEqual(len(found), 1)
        self.assertIn("reviewed on its pull request (changes requested) by adam", found[0]["what"])
        self.assertIn("src/a.ts: this leaks", Path(found[0]["check_dir"], "packet.md").read_text())

    def test_comments_count_only_for_open_tickets_this_machine_reviewed(self) -> None:
        self.watched_project()
        self.reviewed("UIB-1")
        self.ok("ticket", "take", "UIB-2", "--workflow", "review")       # reviewed outside any project
        self.ok("ticket", "take", "UIB-3", "--workflow", "review")
        self.ok("ticket", "take", "UIB-4", "--workflow", "develop")      # worked on, never reviewed
        self.commented = [
            commented("UIB-1", [comment("c1", 5, "new")], state_type="completed"),
            commented("UIB-2", [comment("c2", 5, "new")]),
            commented("UIB-3", [comment("c3", 5, "new")], project="Another project"),
            commented("UIB-4", [comment("c4", 5, "new")]),
        ]

        found = project_watch.poll(NOW + timedelta(minutes=10))["new"]

        # UIB-2 has no project on record and goes to the one that covers its Linear project.
        self.assertEqual([(event["ticket"], event["project"]) for event in found], [("UIB-2", "billing")])
        project_watch.poll(NOW + timedelta(minutes=20))
        self.assertEqual(self.comment_queries[-1], [2, 3, 4])            # the closed ticket is not asked about again

    def test_progress_trigger_sends_new_work_to_the_check(self) -> None:
        self.project(watched=False)
        self.ok("project", "triggers", "billing", "--on", "my progress")
        project_watch.poll(NOW)
        self.issues = [issue("UIB-5", status="In Progress", actor="me", minutes_ago=30)]

        found = project_watch.poll(NOW)["new"]

        self.assertEqual([(event["ticket"], event["state"]) for event in found], [("UIB-5", "checking")])
        packet = Path(found[0]["check_dir"], "packet.md").read_text()
        self.assertIn("answer with exactly one: new_work_large, new_work_small, review_feedback, continuation, noise", packet)
        self.assertIn("Description of UIB-5", packet)
        self.assertNotIn("Written from the current user", packet)

    def test_triggers_are_listed_in_plain_words_for_a_project(self) -> None:
        self.watched_project()

        shown = self.ok("trigger", "list", "--project", "billing")

        self.assertEqual(([row["name"] for row in shown["on"]], [row["name"] for row in shown["off"]]),
                         (["my review"], ["my progress"]))
        row = shown["on"][0]
        self.assertEqual((row["from"], row["on_in_projects"]), ("ready, comes with the skills", ["billing"]))
        self.assertEqual(row["when"][0], "a ticket is moved to In Review; it is assigned to the current user; someone else "
                                         "moved it; not when a chat on this machine already works on the ticket -> starts `review`")
        self.assertIn("a comment appears in Linear for a ticket that was reviewed on this machine", row["when"][1])
        self.assertEqual((row["starts"]["review"], row["starts"]["noise"]),
                         ("/review-task {ticket} (opus, high)", "nothing; one line is recorded"))
        self.assertEqual(row["check"], "sorts the event into one outcome (haiku, low)")

    def test_trigger_file_is_checked_before_it_is_saved(self) -> None:
        self.assertTrue(self.ok("trigger", "check", str(READY_TRIGGERS / "my-progress.yaml"))["ok"])
        broken = self.root / "broken.yaml"
        broken.write_text((READY_TRIGGERS / "my-review.yaml").read_text().replace("to: In Review", "into: In Review"))

        code, _, stderr = self.command("trigger", "check", str(broken))

        self.assertEqual(code, 2)
        self.assertIn("unknown field `into` in a status_changed entry", stderr)

    def test_pause_stops_polling_and_resume_holds_what_came_in(self) -> None:
        self.watched_project()

        self.assertEqual(self.ok("pause")["still_running"], [])
        self.issues = [issue("UIB-1", minutes_ago=30)]
        self.assertIn("paused", project_watch.poll(NOW))
        self.assertEqual(project_watch.cycle(), [])
        self.assertEqual(self.states(), {})
        self.assertTrue(self.ok("status")["watching"].startswith("paused since "))

        resumed = self.ok("resume")

        self.assertTrue(resumed["resumed"])
        self.assertEqual([(event["ticket"], event["state"]) for event in resumed["held"]], [("UIB-1", "held")])
        self.assertEqual(self.ok("resume"), {"resumed": False, "note": "watching was not paused"})

    def test_start_and_dismiss_change_only_events_that_can_change(self) -> None:
        self.project()
        self.issues = [issue("UIB-1"), issue("UIB-2")]
        project_watch.poll(NOW)

        self.assertEqual(self.ok("watch", "start", "1")["events"][0]["state"], "waiting")
        self.assertEqual(self.ok("watch", "dismiss", "2")["events"][0]["state"], "dismissed")
        self.assertEqual(self.states(), {"UIB-1": "waiting", "UIB-2": "dismissed"})
        self.assertEqual([event["ticket"] for event in self.ok("watch", "list")["events"]], ["UIB-1"])

        code, _, stderr = self.command("watch", "dismiss", "1", "2")
        self.assertEqual(code, 2)
        self.assertIn("event 2 is dismissed", stderr)
        self.assertEqual(self.states()["UIB-1"], "waiting")
        self.assertIn("no event 9", self.command("watch", "dismiss", "9")[2])

    def test_waiting_event_starts_a_chat_and_finishes_with_its_report(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]

        lines = project_watch.cycle()

        self.assertEqual(self.states(), {"UIB-1": "started"})
        self.assertIn("UIB-1: review run started", lines)
        self.wait_for_runs()
        call = json.loads(self.log.read_text().splitlines()[0])
        self.assertTrue(call["prompt"].startswith("/project-scope billing /review-task UIB-1\n"))
        self.assertIn('Started by the trigger "my review": UIB-1 was moved from In Progress to In Review', call["prompt"])
        self.assertIn("--worktree", call["argv"])
        self.assertIn("bypassPermissions", call["argv"])
        self.assertEqual(call["argv"][call["argv"].index("--model") + 1], "claude-opus-5-5")

        with patch.object(sys, "stdin", io.StringIO("review report")):
            self.ok("report", "add", "--project", "billing", "--ticket", "UIB-1", "--kind", "review")
        with patch.object(project_watch, "_tell") as tell:
            project_watch.cycle()

        report = self.home / "project-billing" / "reports" / f"{project_watch._stamp()[:10]}-UIB-1-review.md"
        self.assertEqual(tell.call_args.args[1:], (
            "billing", f'UIB-1: review report ready, started by the trigger "my review". {report}'))
        event = project_watch.events(None, True)["events"][0]
        self.assertEqual(event["state"], "finished")
        self.assertTrue(Path(event["run_dir"], "chat.yaml").is_file())
        self.assertEqual(self.ok("status", "--project", "billing")["trigger_events"], [])

    def test_run_that_fails_is_recorded_and_the_project_chat_is_told(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        os.environ["FAKE_MODE"] = "crash"
        project_watch.cycle()
        self.wait_for_runs()

        with patch.object(project_watch, "_tell") as tell:
            lines = project_watch.cycle()

        event = self.ok("status", "--project", "billing")["trigger_events"][0]
        self.assertEqual(event["state"], "failed")
        self.assertIn("boom: no credentials", event["note"])
        self.assertIn("boom: no credentials", lines[0])
        self.assertIn("`agent-projects watch start 1` starts it again", tell.call_args.args[2])
        self.assertIn("review run from the trigger", self.ok("status")["tickets"][0]["last_event"])

        os.environ["FAKE_MODE"] = "ok"
        self.ok("watch", "start", "1")
        project_watch.cycle()
        self.assertEqual(self.states(), {"UIB-1": "started"})
        self.assertTrue(project_watch.events(None, True)["events"][0]["run_dir"].endswith("-2"))

    def test_run_without_a_report_is_passed_on_through_a_small_chat(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        project_watch.cycle()
        self.wait_for_runs()

        project_watch.cycle()
        self.wait_for_runs()

        self.assertEqual(project_watch.events(None, True)["events"][0]["note"], "the run ended without filing a report")
        message = json.loads(self.log.read_text().splitlines()[1])
        self.assertIn('to the chat named "project: Billing"', message["prompt"])
        self.assertIn("select:SendMessage,ListAgents", message["prompt"])
        self.assertIn("ended without filing a report", message["prompt"])
        self.assertEqual(message["argv"][message["argv"].index("--model") + 1], "claude-haiku-5-5")

    def test_run_that_cannot_start_fails_with_the_reason(self) -> None:
        self.watched_project()
        self.issues = [issue("UIB-1", minutes_ago=30)]
        project_watch.poll(NOW)
        self.ok("project", "triggers", "billing", "--off", "my review")
        os.environ[project_watch.TRIGGERS_VARIABLE] = str(self.root / "no-triggers")

        project_watch.cycle()

        event = project_watch.events(None, False)["events"][0]
        self.assertEqual(event["state"], "failed")
        self.assertIn("no longer has the run", event["note"])

    def test_project_triggers_turn_on_and_off(self) -> None:
        self.project(watched=False)

        code, _, stderr = self.command("project", "triggers", "billing", "--on", "no such")
        self.assertEqual(code, 2)
        self.assertIn("no trigger named 'no such'", stderr)

        shown = self.ok("project", "triggers", "billing", "--on", "my review")
        self.assertEqual((shown["triggers"], shown["available"]), (["my review"], ["my progress", "my review"]))
        project_watch.poll(NOW)
        self.assertEqual(project_watch._read_state(self.home)["baseline"], ["billing|my review"])

        self.ok("project", "create", "twin", "--repository", str(self.repo), "--tracker", "linear",
                "--scope", "linear_project=Billing")
        self.assertIn("project billing covers the same tickets",
                      self.ok("project", "triggers", "twin", "--on", "my review")["warnings"][0])

        # Turning a trigger off and on again holds what matches, as the first time.
        self.assertEqual(self.ok("project", "triggers", "billing", "--off", "my review")["triggers"], [])
        self.assertEqual(project_watch._read_state(self.home)["baseline"], [])
        self.assertEqual(self.ok("project", "show", "billing")["triggers"], [])

    def test_triggers_need_the_linear_tracker(self) -> None:
        self.ok("init")
        self.ok("project", "create", "notes", "--repository", str(self.repo))

        code, _, stderr = self.command("project", "triggers", "notes", "--on", "my review")

        self.assertEqual(code, 2)
        self.assertIn("triggers need a project with the linear tracker", stderr)

    def test_init_says_whether_linear_and_watching_work(self) -> None:
        first = self.ok("init")
        self.assertEqual((first["linear"], first["watching"]), ("works, as Ivan", "not running"))

        project_watch.cycle()
        self.key.unlink()
        second = self.ok("init")

        self.assertEqual((second["linear"], second["watching"]), (f"no key: {self.key}", "running"))

    def test_service_file_runs_the_loop_and_spares_running_chats(self) -> None:
        unit = project_watch._unit(Path("/opt/tools/bin/agent-projects"))

        self.assertIn("ExecStart=/opt/tools/bin/agent-projects watch run\n", unit)
        self.assertIn("KillMode=process\n", unit)
        self.assertIn(f'Environment="{agent_projects.HOME_VARIABLE}={self.home}"\n', unit)
        self.assertNotIn("lin_api_test", unit)


if __name__ == "__main__":
    unittest.main()
