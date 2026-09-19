from unittest.mock import MagicMock

import pytest

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.config import NarratorConfig
from log_narrator.engine.models import LogBatch, LogLine


@pytest.mark.asyncio
async def test_stream_diagnostic_yields_thoughts_and_tokens():
    config = NarratorConfig()
    core = AgentDiagnosticCore(config)

    # Mock response with thoughts
    mock_response = MagicMock()
    async def mock_iter(self=None):
        yield "Final diagnosis"
    mock_response.__aiter__ = mock_iter

    async def mock_thoughts():
        yield "Inspecting line 42..."
    mock_response.thoughts = mock_thoughts()

    mock_agent = MagicMock()
    async def mock_chat(prompt):
        return mock_response
    mock_agent.chat = mock_chat
    core._agent = mock_agent

    batch = LogBatch(lines=[LogLine(content="Error", line_number=1)])
    chunks = []
    async for kind, text in core.stream_diagnostic(batch):
        chunks.append((kind, text))

    assert ("thought", "Inspecting line 42...") in chunks
    assert ("token", "Final diagnosis") in chunks
