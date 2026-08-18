"""Small subprocess fixtures for signal and advisory-lock integration tests."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_runner as runner


class SignalTurn:
    id = "signal-turn"

    def __init__(self, ready_path: Path) -> None:
        self.ready_path = ready_path
        self.interrupted = asyncio.Event()

    async def steer(self, _value: str) -> None:
        return None

    async def interrupt(self) -> None:
        self.interrupted.set()

    async def stream(self):
        self.ready_path.write_text("ready\n", encoding="utf-8")
        await self.interrupted.wait()
        turn = SimpleNamespace(
            status=SimpleNamespace(value="interrupted"),
            error=None,
        )
        yield SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(turn=turn),
        )


class SignalThread:
    id = "signal-thread"

    def __init__(self, ready_path: Path) -> None:
        self.ready_path = ready_path

    async def turn(self, _prompt: str, **_kwargs: object) -> SignalTurn:
        return SignalTurn(self.ready_path)


class SignalCodex:
    def __init__(self, ready_path: Path) -> None:
        self.ready_path = ready_path

    async def __aenter__(self) -> "SignalCodex":
        return self

    async def thread_start(self, **_kwargs: object) -> SignalThread:
        return SignalThread(self.ready_path)

    async def close(self) -> None:
        return None


def run_signal(task_path: str, ready_path: str) -> int:
    ready = Path(ready_path)

    def factory(_config: object) -> SignalCodex:
        return SignalCodex(ready)

    invocation = runner.run_invocation(task_path, sdk_factory=factory)
    print(invocation.path.resolve(), flush=True)
    return 0


def hold_lock(cwd: str, ready_path: str, release_path: str) -> int:
    lock = runner.WorktreeLock(cwd)
    if not lock.acquire():
        return 4
    try:
        Path(ready_path).write_text("ready\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not Path(release_path).exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        return 0 if Path(release_path).exists() else 5
    finally:
        lock.release()


if __name__ == "__main__":
    if sys.argv[1] == "signal":
        raise SystemExit(run_signal(sys.argv[2], sys.argv[3]))
    if sys.argv[1] == "hold-lock":
        raise SystemExit(hold_lock(sys.argv[2], sys.argv[3], sys.argv[4]))
    raise SystemExit(2)
