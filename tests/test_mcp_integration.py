from pathlib import Path
from unittest.mock import MagicMock

import pytest

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.config import NarratorConfig


@pytest.mark.asyncio
async def test_agent_core_mcp_servers_config(tmp_path: Path):
    config = NarratorConfig(
        mcp_servers=["k8s=http://localhost:9090/sse"],
        code_root=tmp_path,
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

        assert len(recorded_config.mcp_servers) == 1
        server = recorded_config.mcp_servers[0]
        assert server.name == "k8s"
        assert server.url == "http://localhost:9090/sse"


def test_mcp_stdio_server_with_args_and_prefix():
    from log_narrator.agent.factory import AgentConfigFactory

    config = NarratorConfig(mcp_servers=["db=stdio:my_db_tool --read-only --host localhost"])
    agent_config = AgentConfigFactory.create_agent_config(
        config=config,
        system_prompt="test",
    )
    assert agent_config.mcp_servers is not None
    server = agent_config.mcp_servers[0]
    assert server.name == "db"
    assert server.command == "my_db_tool"
    assert server.args == ["--read-only", "--host", "localhost"]

