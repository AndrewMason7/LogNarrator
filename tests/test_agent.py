import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.antigravity.types import (
    AgentBehavior,
    AntigravityCancelledError,
    AntigravityConnectionError,
    UsageMetadata,
)

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.agent.prompts import build_system_instructions
from log_narrator.agent.tools import create_code_inspection_tool
from log_narrator.config import NarratorConfig
from log_narrator.engine.models import LogBatch, LogLine


def test_prompt_generation():
    prompt_diag = build_system_instructions(mode="diagnostic", target_language="Spanish")
    assert "Spanish" in prompt_diag
    assert "Root Cause" in prompt_diag

    prompt_concise = build_system_instructions(mode="concise", target_language="English")
    assert "1-2 sentence" in prompt_concise

    prompt_structured = build_system_instructions(
        mode="diagnostic", target_language="English", structured_output=True
    )
    assert "**What Happened**:" not in prompt_structured
    assert "[INCIDENT:" not in prompt_structured
    assert "structured JSON payload" in prompt_structured or "finish tool" in prompt_structured

def test_code_inspection_tool(tmp_path: Path):
    source_file = tmp_path / "app.py"
    source_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="app.py", start_line=2, end_line=4)
    assert "line 2" in output
    assert "line 4" in output
    assert "line 5" not in output

def test_code_inspection_blocks_path_traversal(tmp_path: Path):
    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="../../etc/passwd", start_line=1, end_line=5)
    assert "Error: Access denied" in output

def test_code_inspection_blocks_prefix_alias_traversal(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    sibling = tmp_path / "app_secret"
    sibling.mkdir()
    secret_file = sibling / "secret.txt"
    secret_file.write_text("SUPER_SECRET")

    tool_func = create_code_inspection_tool(code_root=root)
    output = tool_func(file_path="../app_secret/secret.txt", start_line=1, end_line=5)
    assert "Error: Access denied" in output
    assert "SUPER_SECRET" not in output

def test_code_inspection_blocks_directory_target(tmp_path: Path):
    sub_dir = tmp_path / "somedir"
    sub_dir.mkdir()
    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="somedir", start_line=1, end_line=5)
    assert "not a valid regular file" in output

def test_code_inspection_blocks_oversized_file(tmp_path: Path):
    large_file = tmp_path / "huge.log"
    # Create file > 10MB without consuming real disk using seek
    with open(large_file, "wb") as f:
        f.seek(11 * 1024 * 1024)
        f.write(b"\0")
    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="huge.log", start_line=1, end_line=5)
    assert "exceeds safety limit" in output


@pytest.mark.asyncio
async def test_agent_core_config_and_capabilities(tmp_path: Path):
    config = NarratorConfig(code_root=tmp_path, api_key="test-key-123")
    core = AgentDiagnosticCore(config)

    # Trigger start without real backend by intercepting Agent constructor
    with pytest.MonkeyPatch.context() as mp:
        recorded_config = None
        def mock_agent_init(self_agent, cfg):
            nonlocal recorded_config
            recorded_config = cfg
        mp.setattr("log_narrator.agent.core.Agent.__init__", mock_agent_init)
        async def mock_aenter(self_agent):
            return MagicMock()
        mp.setattr("log_narrator.agent.core.Agent.__aenter__", mock_aenter)

        await core.start()

        assert recorded_config is not None
        assert recorded_config.capabilities.agent_behavior == AgentBehavior.AUTONOMOUS
        assert recorded_config.workspaces == [str(tmp_path.resolve())]
        assert recorded_config.api_key == "test-key-123"


@pytest.mark.asyncio
async def test_agent_core_antigravity_connection_error():
    config = NarratorConfig()
    core = AgentDiagnosticCore(config)

    mock_agent = MagicMock()
    async def failing_chat(prompt):
        raise AntigravityConnectionError("Endpoint connection refused")

    mock_agent.chat = failing_chat
    core._agent = mock_agent

    batch = LogBatch(lines=[LogLine(content="Error", line_number=1)])
    tokens = []
    async for token in core.stream_narrative(batch):
        tokens.append(token)

    assert any("Connection Error" in t for t in tokens)


@pytest.mark.asyncio
async def test_agent_core_standard_mode_adc():
    config = NarratorConfig(vertex=True, project="enterprise-gcp-99", location="us-east4")
    core = AgentDiagnosticCore(config)

    with pytest.MonkeyPatch.context() as mp:
        recorded_config = None
        def mock_agent_init(self_agent, cfg):
            nonlocal recorded_config
            recorded_config = cfg
        mp.setattr("log_narrator.agent.core.Agent.__init__", mock_agent_init)
        async def mock_aenter(self_agent):
            return MagicMock()
        mp.setattr("log_narrator.agent.core.Agent.__aenter__", mock_aenter)

        await core.start()

        assert recorded_config is not None
        assert recorded_config.vertex is True
        assert recorded_config.project == "enterprise-gcp-99"
        assert recorded_config.location == "us-east4"


@pytest.mark.asyncio
async def test_agent_core_retry_and_budget_config(tmp_path: Path):
    app_dir = tmp_path / "brain"
    config = NarratorConfig(
        max_retries=5,
        max_model_calls=12,
        max_total_tokens=50000,
        app_data_dir=app_dir,
    )
    core = AgentDiagnosticCore(config)

    with pytest.MonkeyPatch.context() as mp:
        recorded_config = None
        def mock_agent_init(self_agent, cfg):
            nonlocal recorded_config
            recorded_config = cfg
        mp.setattr("log_narrator.agent.core.Agent.__init__", mock_agent_init)
        async def mock_aenter(self_agent):
            return MagicMock()
        mp.setattr("log_narrator.agent.core.Agent.__aenter__", mock_aenter)

        await core.start()

        assert recorded_config.retry_config.api_retry.max_retries == 5
        assert recorded_config.budget_config.max_model_calls == 12
        assert recorded_config.budget_config.max_total_tokens == 50000
        assert recorded_config.app_data_dir == str(app_dir.resolve())


@pytest.mark.asyncio
async def test_agent_core_antigravity_cancelled_error():
    config = NarratorConfig()
    core = AgentDiagnosticCore(config)

    mock_agent = MagicMock()
    async def cancelled_chat(prompt):
        raise AntigravityCancelledError("Turn aborted by user")

    mock_agent.chat = cancelled_chat
    core._agent = mock_agent

    batch = LogBatch(lines=[LogLine(content="Error", line_number=1)])
    tokens = []
    with pytest.raises((AntigravityCancelledError, asyncio.CancelledError)):
        async for token in core.stream_narrative(batch):
            tokens.append(token)

    assert any("cancelled" in t.lower() for t in tokens)


def test_agent_core_get_total_usage():
    config = NarratorConfig()
    core = AgentDiagnosticCore(config)
    assert core.get_total_usage() is None

    # Attach mock agent with conversation total usage
    mock_agent = MagicMock()
    mock_usage = UsageMetadata(
        prompt_token_count=100,
        candidates_token_count=50,
        thoughts_token_count=20,
        total_token_count=170,
    )
    mock_agent.conversation.total_usage = mock_usage
    core._agent = mock_agent

    usage = core.get_total_usage()
    assert usage is not None
    assert usage.prompt_token_count == 100
    assert usage.thoughts_token_count == 20
    assert usage.total_token_count == 170


def test_code_inspection_handles_inverted_line_ranges(tmp_path: Path):
    source_file = tmp_path / "app.py"
    source_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="app.py", start_line=4, end_line=2)
    assert "line 4" in output


def test_code_inspection_handles_out_of_bounds_start(tmp_path: Path):
    source_file = tmp_path / "app.py"
    source_file.write_text("line 1\nline 2\n")

    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="app.py", start_line=999, end_line=1005)
    assert "app.py" in output


def test_code_inspection_handles_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("")

    tool_func = create_code_inspection_tool(code_root=tmp_path)
    output = tool_func(file_path="empty.py", start_line=1, end_line=10)
    assert "empty.py" in output




