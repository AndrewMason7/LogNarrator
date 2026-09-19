from unittest.mock import MagicMock

import pytest

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.config import NarratorConfig
from log_narrator.engine.models import IncidentDossier, LogBatch, LogLine


@pytest.mark.asyncio
async def test_agent_core_extracts_structured_output():
    config = NarratorConfig(structured_output=True)
    core = AgentDiagnosticCore(config)
    assert "**What Happened**:" not in core.system_prompt
    assert "structured JSON payload" in core.system_prompt or "finish tool" in core.system_prompt

    mock_response = MagicMock()
    async def mock_iter(self=None):
        yield "Narrative explanation"
    mock_response.__aiter__ = mock_iter
    async def mock_structured():
        return {
            "headline": "Database Deadlock Detected",
            "severity": "CRITICAL",
            "root_cause": "Lock contention on orders table",
            "recommended_fix": "Add index on user_id",
        }
    mock_response.structured_output = mock_structured

    mock_agent = MagicMock()
    async def mock_chat(prompt):
        return mock_response
    mock_agent.chat = mock_chat
    core._agent = mock_agent

    batch = LogBatch(lines=[LogLine(content="Deadlock", line_number=1)])
    dossier = await core.diagnose_batch(batch)

    assert isinstance(dossier, IncidentDossier)
    assert dossier.headline == "Database Deadlock Detected"
    assert dossier.severity == "CRITICAL"


@pytest.mark.asyncio
async def test_coordinator_calls_diagnose_batch_when_structured_output_enabled():
    from unittest.mock import AsyncMock

    from log_narrator.coordinator import PipelineCoordinator

    config = NarratorConfig(structured_output=True, sink="stdout")
    agent_core = MagicMock()
    dossier = IncidentDossier(
        headline="Database connection pool exhausted",
        severity="HIGH",
        root_cause="PostgreSQL connections maxed out",
        recommended_fix="Increase max_connections, Scale pooler",
        affected_components=["db_pool"],
    )
    agent_core.diagnose_batch = AsyncMock(return_value=dossier)
    sink = MagicMock()
    recorder = MagicMock()

    coordinator = PipelineCoordinator(
        config=config,
        agent_core=agent_core,
        sink=sink,
        recorder=recorder,
    )

    batch = LogBatch(lines=[LogLine(content="FATAL: too many connections", line_number=1)])
    await coordinator._process_turn(1, batch)

    agent_core.diagnose_batch.assert_called_once_with(batch)
    sink.stream_token.assert_called()
    recorder.record.assert_called_once()
    recorded_event = recorder.record.call_args[0][0]
    assert recorded_event.headline == dossier.headline


@pytest.mark.asyncio
async def test_coordinator_structured_output_retries_on_rate_limit():
    from log_narrator.coordinator import PipelineCoordinator

    config = NarratorConfig(structured_output=True, max_retries=2, sink="stdout")
    agent_core = MagicMock()
    dossier = IncidentDossier(
        headline="Database connection pool exhausted",
        severity="HIGH",
        root_cause="PostgreSQL connections maxed out",
        recommended_fix="Increase max_connections",
    )
    call_count = 0

    async def mock_diagnose(batch):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("HTTP 429: Resource quota exceeded")
        return dossier

    agent_core.diagnose_batch = mock_diagnose
    sink = MagicMock()
    recorder = MagicMock()

    coordinator = PipelineCoordinator(
        config=config,
        agent_core=agent_core,
        sink=sink,
        recorder=recorder,
    )

    batch = LogBatch(lines=[LogLine(content="FATAL: too many connections", line_number=1)])
    await coordinator._process_turn(1, batch)

    assert call_count == 2
    recorder.record.assert_called_once()
    recorded_event = recorder.record.call_args[0][0]
    assert recorded_event.headline == dossier.headline

