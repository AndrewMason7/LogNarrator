from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.antigravity.types import CompactionConfig

from log_narrator.agent.core import AgentDiagnosticCore
from log_narrator.config import NarratorConfig


@pytest.mark.asyncio
async def test_agent_core_attaches_compaction_config(tmp_path: Path):
    config = NarratorConfig(compaction_token_threshold=50000, code_root=tmp_path)
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

        assert isinstance(recorded_config.compaction_config, CompactionConfig)
        assert recorded_config.compaction_config.token_threshold == 50000
