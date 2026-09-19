from pathlib import Path

from google.antigravity import LocalAgentConfig, LocalOpenAIAgentConfig
from google.antigravity.types import CompactionConfig

from log_narrator.agent.factory import AgentConfigFactory
from log_narrator.config import NarratorConfig


def test_factory_creates_local_openai_config(tmp_path: Path):
    config = NarratorConfig(
        local_url="http://localhost:11434/v1",
        local_model="gemma2:9b",
        code_root=tmp_path,
        compaction_token_threshold=40000,
    )
    agent_config = AgentConfigFactory.create_agent_config(
        config=config,
        system_prompt="Test instructions",
        tools=[],
    )
    assert isinstance(agent_config, LocalOpenAIAgentConfig)
    assert agent_config.base_url == "http://localhost:11434/v1"
    assert agent_config.model == "gemma2:9b"
    assert isinstance(agent_config.compaction_config, CompactionConfig)
    assert agent_config.compaction_config.token_threshold == 40000

def test_factory_creates_gemini_cloud_config(tmp_path: Path):
    config = NarratorConfig(
        model="gemini-3.7-flash",
        api_key="secret-key",
        code_root=tmp_path,
    )
    agent_config = AgentConfigFactory.create_agent_config(
        config=config,
        system_prompt="Cloud instructions",
        tools=[],
    )
    assert isinstance(agent_config, LocalAgentConfig)
    assert agent_config.model == "gemini-3.7-flash"
    assert agent_config.api_key == "secret-key"


def test_factory_configures_policies(tmp_path: Path):
    config = NarratorConfig(code_root=tmp_path, api_key="secret-key")
    agent_config = AgentConfigFactory.create_agent_config(
        config=config,
        system_prompt="Test instructions",
        tools=[],
    )
    assert agent_config.policies is not None
    assert agent_config.policies[0].tool == "run_command"
    assert agent_config.policies[0].decision.name == "DENY"
    assert agent_config.policies[-1].tool == "*"
    assert agent_config.policies[-1].decision.name == "APPROVE"

