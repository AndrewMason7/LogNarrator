import asyncio
import sys
from collections.abc import AsyncIterator

from log_narrator.ingestion.base import BaseLogReader


class StdinReader(BaseLogReader):
    """Reads lines from standard input asynchronously without blocking the event loop."""

    def __init__(self) -> None:
        self._running = True

    async def stream(self) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        try:
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            while self._running:
                line_bytes = await reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace").rstrip("\r\n")
                yield line
        except Exception:
            # Fallback for systems/environments where connect_read_pipe isn't supported
            while self._running:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                yield line.rstrip("\r\n")

    async def stop(self) -> None:
        self._running = False
