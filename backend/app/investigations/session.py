"""Investigation sessions and their progress event log.

ponytail: in-memory only, so sessions die with the process and won't work
across multiple workers. Swap the dict for Redis/Postgres if the demo ever
needs to survive a restart or scale past one process.
"""
import asyncio
import uuid
from datetime import datetime, timezone


class Investigation:
    def __init__(self, question: str):
        self.id = uuid.uuid4().hex[:12]
        self.question = question
        self.status = "running"
        self.result = None
        self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.events = []
        self._changed = asyncio.Event()

    def add_event(self, event: dict):
        self.events.append(event)
        self._changed.set()

    def finish(self, result: dict, status: str):
        self.status = status
        self.result = result
        self._changed.set()

    @property
    def done(self) -> bool:
        return self.status != "running"

    async def stream(self):
        """Yields every event from the start, then waits for new ones.

        Replaying from index 0 matters: the frontend usually connects a moment
        after POSTing, and without replay it would silently miss whatever the
        agent already emitted.
        """
        index = 0
        while True:
            while index < len(self.events):
                yield self.events[index]
                index += 1
            if self.done:
                return
            await self._changed.wait()
            self._changed.clear()

    def summary(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "status": self.status,
            "created_at": self.created_at,
            "result": self.result,
        }


# id -> Investigation
STORE: dict[str, Investigation] = {}
