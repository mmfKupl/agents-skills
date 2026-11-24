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
        "state": {"name": status},
        "assignee": {"id": assignee, "name": assignee} if assignee else None,
        "history": {"nodes": [
            {"id": f"{identifier}-edit", "createdAt": NOW.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
             "actor": {"id": "other", "name": "Other"}, "botActor": None, "fromState": None, "toState": None},
            {"id": move_id or f"{identifier}-move", "createdAt": moved,
             "actor": {"id": actor, "name": actor.title()} if actor else None, "botActor": None,
             "fromState": {"name": "In Progress"}, "toState": {"name": moved_to or status}},
        ]},
    }


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
        self.queries: list[dict] = []
        patcher = patch.object(project_watch, "linear", self.fake_linear)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.wait_for_runs)

    def fake_linear(self, query: str, variables: dict | None = None, timeout: float = 30) -> dict:
        if "viewer" in query:
            return {"viewer": {"id": "me", "name": "Ivan"}}
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
        self.assertEqual(self.ok("trigger", "list")["triggers"][0]["name"], "my review")

    def test_trigger_the_script_does_not_understand_is_refused(self) -> None:
        good = (READY_TRIGGERS / "my-review.yaml").read_text()
        cases = {
            "unknown field `assigne`": good.replace("assignee:", "assigne:"),
            "reads only": good.replace("status_changed", "comment_added"),
            "`then` must name": good.replace("then: review", "then: revew"),
            "unknown model": good.replace("model: opus", "model: gpt-9"),
            "`effort` must be": good.replace("effort: high", "effort: huge"),
            "`assignee` must be": good.replace("assignee: current_user", "assignee: me"),
            "unknown field `check`": good + "check:\n  model: haiku\n",
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
        document.write_text(document.read_text().replace("- my review", "- my progress"))
        self.assertEqual(project_watch.poll(NOW)["problems"], ["project billing: no trigger named 'my progress'"])
        self.assertEqual(project_watch.events(None, True)["problems"], ["project billing: no trigger named 'my progress'"])

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

        code, _, stderr = self.command("project", "triggers", "billing", "--on", "my progress")
        self.assertEqual(code, 2)
        self.assertIn("no trigger named 'my progress'", stderr)

        shown = self.ok("project", "triggers", "billing", "--on", "my review")
        self.assertEqual((shown["triggers"], shown["available"]), (["my review"], ["my review"]))
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
