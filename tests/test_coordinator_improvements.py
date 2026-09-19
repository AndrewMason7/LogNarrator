from unittest.mock import MagicMock

import pytest

from log_narrator.config import NarratorConfig
from log_narrator.coordinator import RATE_LIMIT_PATTERN, PipelineCoordinator
from log_narrator.engine.models import LogBatch, LogLine
from log_narrator.sinks.stdout_sink import StdoutSink


@pytest.mark.asyncio
async def test_sink_registry_dispatch():
    config = NarratorConfig(sink="stdout")
    coord = PipelineCoordinator(config)
    assert isinstance(coord.sink, StdoutSink)

def test_rate_limit_pattern_precision():
    # True positives
    assert RATE_LIMIT_PATTERN.search("HTTP 429 Too Many Requests")
    assert RATE_LIMIT_PATTERN.search("Resource quota exceeded")
    assert RATE_LIMIT_PATTERN.search("API rate limit hit")
    # False positives that must NOT trigger backoff
    assert not RATE_LIMIT_PATTERN.search("Connected to port 4290")
    assert not RATE_LIMIT_PATTERN.search("Worker 429 exited with status 0")
    assert not RATE_LIMIT_PATTERN.search("Issue #4291 created")

@pytest.mark.asyncio
async def test_process_turn_buffers_tokens_and_polymorphic_stream():
    config = NarratorConfig()
    mock_agent = MagicMock()
    
    async def mock_stream_diagnostic(batch):
        yield ("thought", "thinking hard")
        yield ("token", "Incident ")
        yield ("token", "detected!")
        
    mock_agent.stream_diagnostic = mock_stream_diagnostic
    mock_agent.pop_inspected_files.return_value = []
    mock_sink = MagicMock()
    mock_recorder = MagicMock()
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = None

    coord = PipelineCoordinator(
        config=config,
        agent_core=mock_agent,
        sink=mock_sink,
        recorder=mock_recorder,
        extractor=mock_extractor,
    )

    batch = LogBatch(source="test.log", lines=[LogLine(content="error line")])
    await coord._process_turn(1, batch)

    # Verify thoughts and tokens routed
    mock_sink.stream_thought.assert_called_once_with("thinking hard")
    assert mock_sink.stream_token.call_count == 2
    # Verify extractor received full joined response
    mock_extractor.extract.assert_called_once_with(1, batch, "Incident detected!", inspected_files=[])


@pytest.mark.asyncio
async def test_coordinator_retries_on_rate_limit():
    config = NarratorConfig(max_retries=2)
    agent_core = MagicMock()
    # Fails once with 429, then succeeds
    async def mock_stream(batch):
        if agent_core.call_count == 0:
            agent_core.call_count += 1
            raise Exception("HTTP 429 Too Many Requests: quota exceeded")
        agent_core.call_count += 1
        yield "token", "Analysis successful"

    agent_core.call_count = 0
    agent_core.stream_diagnostic = mock_stream
    sink = MagicMock()

    coordinator = PipelineCoordinator(
        config=config,
        agent_core=agent_core,
        sink=sink,
    )
    batch = LogBatch(lines=[LogLine(content="error", line_number=1)])
    await coordinator._process_turn(1, batch)

    assert agent_core.call_count == 2

