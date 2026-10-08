"""Injectable wall/monotonic clocks and one cancellable deadline task."""
import asyncio
from dataclasses import dataclass
import time
from typing import Awaitable, Callable


@dataclass(frozen=True)
class Clock:
    utc: Callable[[], float] = time.time
    monotonic: Callable[[], float] = time.monotonic


class DeadlineTimer:
    """No sockets; invokes service's serialized timeout path at the deadline."""

    def __init__(self, clock: Clock):
        self.clock = clock
        self._task: asyncio.Task | None = None

    def cancel(self) -> None:
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
        self._task = None

    def schedule(self, deadline: float, callback: Callable[[], Awaitable[bool]]) -> None:
        self.cancel()

        async def wait() -> None:
            while True:
                await asyncio.sleep(max(0, deadline - self.clock.monotonic()))
                if self.clock.monotonic() < deadline:
                    continue
                if await callback():
                    return
                # Failed persistence must not silently discard the active timeout.
                await asyncio.sleep(0.1)

        self._task = asyncio.create_task(wait(), name="auction-deadline")

    async def close(self) -> None:
        task = self._task
        self.cancel()
        if task is not None and task is not asyncio.current_task():
            try:
                await task
            except asyncio.CancelledError:
                pass
