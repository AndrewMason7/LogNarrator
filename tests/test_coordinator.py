import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from log_narrator.config import NarratorConfig
from log_narrator.coordinator import PipelineCoordinator
from log_narrator.engine.models import LogBatch, LogLine
from log_narrator.ingestion.base import BaseLogReader
from log_narrator.sinks.base import BaseOutputSink


class MockLogReader(BaseLogReader):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.stopped = False

    async def stream(self) -> AsyncIterator[str]:
        for line in self.lines:
            if self.stopped:
                break
            yield line

    async def stop(self) -> None:
        self.stopped = True

class MockSink(BaseOutputSink):
    def __init__(self) -> None:
        self.emitted_lines: list[str] = []
        self.tokens: list[str] = []
        self.turns_started: list[int] = []
        self.closed = False

    def emit_raw_log(self, line: str) -> None:
        self.emitted_lines.append(line)

    def start_turn(self, turn_id: int) -> None:
        self.turns_started.append(turn_id)

    def stream_token(self, token: str) -> None:
        self.tokens.append(token)

    def end_turn(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

@pytest.mark.asyncio
async def test_pipeline_coordinator_real_execution_dataflow():
    config = NarratorConfig(debounce_seconds=0.05, max_batch_lines=2)
    reader = MockLogReader(["ERROR line 1", "ERROR line 2"])
    sink = MockSink()
    mock_agent = MagicMock()
    mock_agent.start = AsyncMock()
    mock_agent.stop = AsyncMock()

    async def mock_stream_diagnostic(batch: LogBatch):
        yield ("token", f"Diagnosed {len(batch.lines)} lines")

    mock_agent.stream_diagnostic = mock_stream_diagnostic

    coordinator = PipelineCoordinator(
        config=config,
        reader=reader,
        sink=sink,
        agent_core=mock_agent,
    )

    await coordinator.run()

    # Verify real dataflow truth
    assert sink.emitted_lines == ["ERROR line 1", "ERROR line 2"]
    mock_agent.start.assert_awaited_once()
    mock_agent.stop.assert_awaited_once()
    assert sink.tokens == ["Diagnosed 2 lines"]
    assert 1 in sink.turns_started
    assert sink.closed is True

@pytest.mark.asyncio
async def test_coordinator_429_backoff_zero_delay(monkeypatch):
    config = NarratorConfig()
    sink = MockSink()
    coordinator = PipelineCoordinator(config=config, sink=sink)

    sleep_calls = []
    async def fast_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    async def fail_with_quota(batch):
        raise RuntimeError("HTTP 429: Resource has been exhausted (e.g. check quota)")
        yield ""

    coordinator.agent_core.stream_diagnostic = fail_with_quota

    batch = LogBatch(lines=[LogLine(content="Error", line_number=1)])
    await coordinator._process_turn(1, batch)

    assert len(sleep_calls) == 2
    assert sleep_calls[0] >= 1.0
    assert sleep_calls[1] >= 2.0
    assert any("429" in t for t in sink.tokens)

@pytest.mark.asyncio
async def test_coordinator_shutdown_timeout(monkeypatch):
    config = NarratorConfig()
    sink = MockSink()
    reader = MockLogReader([])
    coordinator = PipelineCoordinator(config=config, reader=reader, sink=sink)

    # Mock agent core stop to hang forever
    async def hanging_stop():
        await asyncio.sleep(100.0)

    coordinator.agent_core.stop = hanging_stop
    coordinator.agent_core.start = AsyncMock()

    # Fast-forward wait_for timeout to 0.05s so test doesn't wait 3 real seconds
    orig_wait_for = asyncio.wait_for
    async def fast_wait_for(fut, timeout):
        return await orig_wait_for(fut, timeout=0.05)

    monkeypatch.setattr(asyncio, "wait_for", fast_wait_for)
    await coordinator.run()
    assert sink.closed is True


@pytest.mark.asyncio
async def test_coordinator_idle_session_reset():
    config = NarratorConfig(idle_reset_seconds=10.0)
    agent_core = MagicMock()
    agent_core.reset = AsyncMock()
    agent_core.stream_diagnostic = MagicMock(return_value=AsyncMock())
    sink = MagicMock()
    coordinator = PipelineCoordinator(config=config, agent_core=agent_core, sink=sink)

    # Set last turn time in the past
    coordinator._last_turn_time = 0.0
    batch = LogBatch(lines=[LogLine(content="Line", line_number=1)])

    async def mock_diag(b):
        yield "token", "diag"

    agent_core.stream_diagnostic = mock_diag

    await coordinator._process_turn(1, batch)
    agent_core.reset.assert_awaited_once()

