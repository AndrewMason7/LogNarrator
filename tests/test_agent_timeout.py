import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.config import NarratorConfig
from log_narrator.engine.models import LogBatch, LogLine


@pytest.mark.asyncio
async def test_stream_narrative_handles_turn_timeout():
    config = NarratorConfig()
    core = AgentDiagnosticCore(config)

    # Mock an agent that hangs forever
    mock_agent = MagicMock()
    async def infinite_chat(prompt):
        await asyncio.sleep(10.0)
        return AsyncMock()

    mock_agent.chat = infinite_chat
    core._agent = mock_agent

    batch = LogBatch(lines=[LogLine(content="Error", line_number=1)])
    tokens = []
    async for token in core.stream_narrative(batch, timeout_seconds=0.1):
        tokens.append(token)

    assert any("Timeout" in t for t in tokens)
