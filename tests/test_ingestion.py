import asyncio
from pathlib import Path

import pytest

from log_narrator.ingestion.file_tailer import FileTailer


@pytest.mark.asyncio
async def test_file_tailer_reads_lines(tmp_path: Path):
    log_file = tmp_path / "test.log"
    log_file.write_text("line 1\nline 2\n")

    tailer = FileTailer(log_file, from_beginning=True, poll_interval=0.05)
    collected = []

    async def consume():
        async for line in tailer.stream():
            collected.append(line)
            if len(collected) == 3:
                await tailer.stop()
                break

    consumer_task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)
    with open(log_file, "a") as f:
        f.write("line 3\n")
    
    await asyncio.wait_for(consumer_task, timeout=2.0)
    assert collected == ["line 1", "line 2", "line 3"]
