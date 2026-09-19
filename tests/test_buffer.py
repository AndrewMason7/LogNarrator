import asyncio

import pytest

from log_narrator.engine.buffer import LogBuffer
from log_narrator.engine.preprocessor import LogPreprocessor


@pytest.mark.asyncio
async def test_buffer_debouncing_and_batch_emission():
    preprocessor = LogPreprocessor(ignored_patterns=[r"GET /health 200"])
    buffer = LogBuffer(preprocessor=preprocessor, debounce_seconds=0.2, max_batch_lines=5)

    await buffer.push("INFO: start worker")
    await buffer.push("GET /health 200")  # Should be dropped
    await buffer.push("WARN: high memory load")

    # Wait for debounce timer to expire
    batch = await asyncio.wait_for(buffer.get_next_batch(), timeout=1.0)
    assert batch is not None
    assert batch.total_lines == 2
    assert "start worker" in batch.raw_text
    assert "health" not in batch.raw_text

@pytest.mark.asyncio
async def test_buffer_caps_at_max_lines():
    preprocessor = LogPreprocessor(ignored_patterns=[])
    buffer = LogBuffer(preprocessor=preprocessor, debounce_seconds=5.0, max_batch_lines=3)

    await buffer.push("line 1")
    await buffer.push("line 2")
    await buffer.push("line 3")  # Max lines reached, should emit immediately without waiting 5s

    batch = await asyncio.wait_for(buffer.get_next_batch(), timeout=0.5)
    assert batch.total_lines == 3

@pytest.mark.asyncio
async def test_buffer_hard_deadline_flushes():
    preprocessor = LogPreprocessor(ignored_patterns=[])
    # Long debounce (2.0s), but short hard deadline (0.3s)
    buffer = LogBuffer(preprocessor=preprocessor, debounce_seconds=2.0, max_wait_seconds=0.3, max_batch_lines=50)

    await buffer.push("line 1")
    await asyncio.sleep(0.15)
    await buffer.push("line 2")
    await asyncio.sleep(0.2)
    # Total elapsed > 0.3s -> should force flush on next line
    await buffer.push("line 3")

    batch = await asyncio.wait_for(buffer.get_next_batch(), timeout=0.5)
    assert batch is not None
    assert batch.total_lines == 3


@pytest.mark.asyncio
async def test_buffer_close_is_idempotent():
    prep = LogPreprocessor([])
    buf = LogBuffer(preprocessor=prep)
    await buf.close()
    await buf.close()  # second call should be a no-op

    first = await buf.get_next_batch()
    assert first is None
    # Ensure queue only has one None, not two
    assert buf._queue.empty()

