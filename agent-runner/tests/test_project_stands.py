from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_projects  # noqa: E402
import project_stands  # noqa: E402
from agent_projects import ProjectsError  # noqa: E402

# Stands in for the repository's script: it says which project it would start and
# writes down every call, with the heap it was given.
FAKE_SCRIPT = """#!/bin/sh
echo "$* heap=$UI_BAKERY_DEV_NODE_HEAP_MB" >> "$(dirname "$0")/calls.log"
case "$1" in
  project) echo "Compose project: uibakery-$(basename "$(git rev-parse --show-toplevel)")" ;;
  url) echo "http://127.0.0.1:4321" ;;
esac
"""


class StandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        self.home = self.folder / "agent-projects"
        self.home.mkdir()
        patches = [
            patch.dict(os.environ, {agent_projects.HOME_VARIABLE: str(self.home)}),
            patch.object(project_stands, "_docker", side_effect=self.docker),
            patch.object(project_stands, "_running", return_value={}),
            patch.object(project_stands, "POLL_SECONDS", 0.01),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.free = 20.0
        memory = patch.object(project_stands, "_available_gb", side_effect=lambda: self.free)
        memory.start()
        self.addCleanup(memory.stop)
        self.docker_calls: list[tuple[str, ...]] = []

    def docker(self, *words: str) -> list[str]:
        self.docker_calls.append(words)
        return ["c1"] if words[:2] == ("ps", "-aq") else []

    def worktree(self, name: str) -> Path:
        root = self.folder / name
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        script = root / project_stands.SCRIPT
        script.parent.mkdir(parents=True)
        script.write_text(FAKE_SCRIPT)
        script.chmod(0o755)
        return root

    def calls(self, root: Path) -> list[str]:
        return (root / project_stands.SCRIPT).parent.joinpath("calls.log").read_text().splitlines()

    def stands(self) -> list[dict]:
        return project_stands._load(self.home / project_stands.STANDS_FILE)

    def test_stand_starts_with_a_small_heap_and_is_recorded_with_who_and_why(self) -> None:
        root = self.worktree("one")
        answer = project_stands.stand_take(["bakery", "back"], "UIB-1: video of the editor", 20, "UIB-1", 0, str(root))

        self.assertEqual((answer["stand"], answer["url"]), ("uibakery-one", "http://127.0.0.1:4321"))
        self.assertIn(f"up bakery back heap={project_stands.HEAP_MB}", self.calls(root))
        [stand] = self.stands()
        self.assertEqual((stand["why"], stand["ticket"], stand["services"], stand["state"]),
                         ("UIB-1: video of the editor", "UIB-1", ["back", "bakery"], "running"))

    def test_stand_waits_while_memory_is_short_and_says_who_holds_it(self) -> None:
        first, second = self.worktree("one"), self.worktree("two")
        project_stands.stand_take(["bakery", "workbench", "back"], "UIB-1: video", 30, None, 0, str(first))
        self.free = 9.0    # enough for the stand alone, but the first is still growing and will take its share

        with self.assertRaises(ProjectsError) as raised:
            project_stands.stand_take(["bakery"], "UIB-2: screenshot", 30, None, 0, str(second))

        self.assertIn("uibakery-one: UIB-1: video, back, bakery, workbench, running", str(raised.exception))
        self.assertNotIn("up bakery", "\n".join(self.calls(second)))
        # Once the first has grown, only what the kernel says is free counts.
        stand = self.stands()[0]
        stand["started"] = project_stands._stamp(project_stands._now() - timedelta(minutes=30))
        project_stands._save(self.home / project_stands.STANDS_FILE, [stand])
        project_stands.stand_take(["bakery"], "UIB-2: screenshot", 30, None, 0, str(second))
        self.assertEqual([item["name"] for item in self.stands()], ["uibakery-one", "uibakery-two"])

    def test_done_removes_the_stand_and_keep_only_stops_it(self) -> None:
        root = self.worktree("one")
        project_stands.stand_take(["back"], "UIB-1: API check", 30, None, 0, str(root))

        self.assertEqual(project_stands.stand_done(True, str(root))["state"], "stopped, its databases kept")
        self.assertEqual(self.stands()[0]["state"], "stopped")
        self.assertIn(("stop", "c1"), self.docker_calls)
        self.assertEqual(project_stands.stand_done(False, str(root))["state"], "removed")
        self.assertEqual(self.stands(), [])
        self.assertIn(("rm", "-f", "c1"), self.docker_calls)
        self.assertTrue(any(line.startswith("cleanup") for line in self.calls(root)))

    def test_sweep_stops_a_stand_whose_chat_ended_and_removes_one_whose_worktree_is_gone(self) -> None:
        left, gone = self.worktree("left"), self.worktree("gone")
        for root in (left, gone):
            project_stands.stand_take(["back"], "check", 30, None, 0, str(root))
        stands = self.stands()
        stands[0].update(pid=999999999, pid_start="1")    # a process that does not exist
        project_stands._save(self.home / project_stands.STANDS_FILE, stands)
        subprocess.run(["rm", "-rf", str(gone)], check=True)

        done = project_stands.sweep()

        self.assertEqual(done, ["stopped the stand uibakery-left: the chat that took it has ended",
                                "removed the stand uibakery-gone: its worktree is gone"])
        self.assertEqual([(item["name"], item["state"]) for item in self.stands()], [("uibakery-left", "stopped")])
        later = project_stands._now() + project_stands.STOPPED_KEPT + timedelta(minutes=1)
        self.assertEqual(project_stands.sweep(later), ["removed the stand uibakery-left: stopped for a day"])

    def test_list_shows_stands_no_chat_recorded(self) -> None:
        with patch.object(project_stands, "_running", return_value={"uibakery-x": "/w/x"}):
            listed = project_stands.stand_list()
        self.assertEqual((listed["memory_free_gb"], listed["not_recorded"]), (20.0, [{"name": "uibakery-x", "worktree": "/w/x"}]))


if __name__ == "__main__":
    unittest.main()
