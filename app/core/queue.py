import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class MessageQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    def set_handler(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._handler = handler

    async def enqueue(self, payload: dict[str, Any]) -> None:
        await self._queue.put(payload)
        logger.debug("Enqueued message payload, queue size: %d", self._queue.qsize())

    async def process_loop(self) -> None:
        self._running = True
        logger.info("Message queue processing loop started")
        while self._running:
            try:
                payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                if self._handler:
                    await self._handler(payload)
                else:
                    logger.warning("No handler set, dropping payload")
            except Exception:
                logger.exception("Error processing queued message")
            finally:
                self._queue.task_done()

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self.process_loop())

    async def shutdown(self) -> None:
        logger.info("Shutting down message queue, draining %d items", self._queue.qsize())
        self._running = False
        if not self._queue.empty():
            await self._queue.join()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Message queue shut down")


message_queue = MessageQueue()
