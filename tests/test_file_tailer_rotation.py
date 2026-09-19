import asyncio
from pathlib import Path

import pytest

from log_narrator.ingestion.file_tailer import FileTailer


@pytest.mark.asyncio
async def test_file_tailer_detects_truncation(tmp_path: Path):
    log_file = tmp_path / "app.log"
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

    # Simulate truncation: file is emptied and new line written
    log_file.write_text("line 3 after truncate\n")

    await asyncio.wait_for(consumer_task, timeout=2.0)
    assert "line 1" in collected
    assert "line 3 after truncate" in collected


@pytest.mark.asyncio
async def test_file_tailer_detects_inode_rotation(tmp_path: Path):
    log_file = tmp_path / "app.log"
    log_file.write_text("old file line 1\n")

    tailer = FileTailer(log_file, from_beginning=True, poll_interval=0.05)
    collected = []

    async def consume():
        async for line in tailer.stream():
            collected.append(line)
            if len(collected) == 2:
                await tailer.stop()
                break

    consumer_task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)

    # Simulate logrotate: rename old file and create brand new file with different inode
    rotated_file = tmp_path / "app.log.1"
    log_file.rename(rotated_file)
    log_file.write_text("new file line after rotation\n")

    await asyncio.wait_for(consumer_task, timeout=2.0)
    assert "old file line 1" in collected
    assert "new file line after rotation" in collected

