import asyncio
import logging
import time

from log_narrator.engine.models import LogBatch, LogLine
from log_narrator.engine.preprocessor import LogPreprocessor

logger = logging.getLogger(__name__)

class LogBuffer:
    """Buffers lines, debounces bursts with hard deadline caps, and emits LogBatch instances."""

    def __init__(
        self,
        preprocessor: LogPreprocessor,
        debounce_seconds: float = 1.5,
        max_batch_lines: int = 50,
        max_wait_seconds: float = 5.0,
        max_queue_size: int = 100,
        source_name: str = "stream",
    ) -> None:
        self.preprocessor = preprocessor
        self.debounce_seconds = debounce_seconds
        self.max_batch_lines = max_batch_lines
        self.max_wait_seconds = max_wait_seconds
        self.source_name = source_name

        self._pending_lines: list[LogLine] = []
        self._queue: asyncio.Queue[LogBatch | None] = asyncio.Queue(maxsize=max_queue_size)
        self._debounce_task: asyncio.Task[None] | None = None
        self._first_line_time: float | None = None
        self._line_counter = 0
        self._in_multiline = False
        self._is_closed = False

    async def push(self, line_text: str) -> None:
        if self._is_closed or self.preprocessor.is_ignored(line_text):
            return

        now = time.monotonic()
        if not self._pending_lines:
            self._first_line_time = now

        self._line_counter += 1
        is_cont = False

        if self.preprocessor.is_multiline_start(line_text):
            self._in_multiline = True
        elif self._in_multiline:
            if self.preprocessor.is_multiline_continuation(line_text):
                is_cont = True
            else:
                self._in_multiline = False

        log_line = LogLine(
            content=line_text,
            line_number=self._line_counter,
            is_multiline_continuation=is_cont,
        )
        self._pending_lines.append(log_line)

        # Flush if line cap reached OR hard deadline exceeded
        hard_deadline_expired = (
            self._first_line_time is not None and (now - self._first_line_time) >= self.max_wait_seconds
        )
        if len(self._pending_lines) >= self.max_batch_lines or hard_deadline_expired:
            await self._flush()
            return

        # Restart debounce timer
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._wait_and_flush())

    async def _wait_and_flush(self) -> None:
        try:
            await asyncio.sleep(self.debounce_seconds)
            await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        if not self._pending_lines:
            return

        batch = LogBatch(lines=list(self._pending_lines), source=self.source_name)
        self._pending_lines.clear()
        self._first_line_time = None
        self._in_multiline = False
        
        # Handle queue overflow gracefully without blocking by evicting oldest item
        try:
            self._queue.put_nowait(batch)
        except asyncio.QueueFull:
            try:
                _ = self._queue.get_nowait()
                self._queue.put_nowait(batch)
            except Exception as e:
                logger.warning("Failed to evict oldest batch on queue overflow: %s", e)

    async def get_next_batch(self) -> LogBatch | None:
        return await self._queue.get()

    async def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        await self._flush()
        await self._queue.put(None)
