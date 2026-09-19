import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles

from log_narrator.ingestion.base import BaseLogReader


class FileTailer(BaseLogReader):
    """Asynchronously tails a file on disk, handling append updates and EOF waits."""

    def __init__(
        self,
        file_path: Path,
        from_beginning: bool = False,
        poll_interval: float = 0.1,
    ) -> None:
        self.file_path = Path(file_path)
        self.from_beginning = from_beginning
        self.poll_interval = poll_interval
        self._running = True

    async def stream(self) -> AsyncIterator[str]:
        # Wait until file exists if started early
        while self._running and not self.file_path.exists():
            await asyncio.sleep(self.poll_interval)

        current_inode = self.file_path.stat().st_ino if self.file_path.exists() else None

        while self._running:
            try:
                async with aiofiles.open(self.file_path, encoding="utf-8", errors="replace") as f:
                    if not self.from_beginning:
                        await f.seek(0, 2)  # Seek to end of file
                    self.from_beginning = True

                    buffer = ""
                    first_bytes = None
                    while self._running:
                        if self.file_path.exists():
                            stat = self.file_path.stat()
                            current_pos = await f.tell()
                            is_truncated = stat.st_size < current_pos

                            # Check if file was overwritten/truncated with longer content
                            if not is_truncated and first_bytes and current_pos > 0 and stat.st_size != current_pos:
                                await f.seek(0, 0)
                                sample = await f.read(len(first_bytes))
                                if sample != first_bytes:
                                    is_truncated = True
                                else:
                                    await f.seek(current_pos, 0)

                            if is_truncated:
                                await f.seek(0, 0)
                                buffer = ""
                                first_bytes = None
                            elif current_inode and stat.st_ino != current_inode:
                                current_inode = stat.st_ino
                                break

                        chunk = await f.read(65536)
                        if chunk:
                            if first_bytes is None:
                                first_bytes = chunk[:64]
                            buffer += chunk
                            lines = buffer.split("\n")
                            buffer = lines.pop()  # Keep uncompleted trailing line fragment in buffer
                            for line in lines:
                                yield line.rstrip("\r")
                        else:
                            await asyncio.sleep(self.poll_interval)
            except FileNotFoundError:
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False

