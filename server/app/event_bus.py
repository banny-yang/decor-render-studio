import asyncio
from collections import defaultdict


class EventBus:
    """进程内发布/订阅，用于 SSE 推送任务进度。key 形如 "task:12"。"""

    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[key].append(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue):
        try:
            self._subs[key].remove(q)
        except ValueError:
            pass
        if not self._subs[key]:
            self._subs.pop(key, None)

    async def publish(self, key: str, message: dict):
        for q in list(self._subs.get(key, [])):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass


bus = EventBus()
