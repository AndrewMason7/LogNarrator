import shlex
from collections.abc import Callable
from typing import Any

from google.antigravity import (
    LocalAgentConfig,
    LocalOpenAIAgentConfig,
    types,
)
from google.antigravity.connections.local.local_connection_config import (
    BaseLocalAgentConfig,
)
from google.antigravity.hooks import policy
from google.antigravity.types import (
    AgentBehavior,
    BudgetConfig,
    CapabilitiesConfig,
    CompactionConfig,
    ModelAPIRetryConfig,
    ModelOutputRetryConfig,
    RetryConfig,
)

from log_narrator.config import NarratorConfig
from log_narrator.engine.models import IncidentDossier


class AgentConfigFactory:
    """Factory responsible for assembling Google Antigravity Agent configurations."""

    @staticmethod
    def create_agent_config(
        config: NarratorConfig,
        system_prompt: str,
        tools: list[Callable[..., Any]] | None = None,
    ) -> BaseLocalAgentConfig:
        capabilities = CapabilitiesConfig(
            agent_behavior=AgentBehavior.AUTONOMOUS,
        )
        policies = [
            policy.deny("run_command"),
            policy.workspace_only([str(config.code_root.resolve())]),
            policy.allow("*"),
        ]
        retry_config = RetryConfig(
            api_retry=ModelAPIRetryConfig(
                max_retries=config.max_retries,
                initial_sleep_duration_ms=1000,
                exponential_multiplier=2.0,
                jitter_range=0.1,
            ),
            model_output_retry=ModelOutputRetryConfig(max_retries=2),
        )
        budget_config = None
        if config.max_model_calls or config.max_total_tokens:
            budget_config = BudgetConfig(
                max_model_calls=config.max_model_calls,
                max_total_tokens=config.max_total_tokens,
            )

        app_data_dir = (
            str(config.app_data_dir.resolve())
            if config.app_data_dir
            else None
        )

        compaction_config = (
            CompactionConfig(token_threshold=config.compaction_token_threshold)
            if config.compaction_token_threshold
            else None
        )

        mcp_server_configs = []
        for spec in config.mcp_servers:
            if "=" in spec:
                name, endpoint = spec.split("=", 1)
                name = name.strip()
                endpoint = endpoint.strip()
                if endpoint.startswith("http://") or endpoint.startswith("https://"):
                    mcp_server_configs.append(
                        types.McpStreamableHttpServer(name=name, url=endpoint)
                    )
                else:
                    cmd_str = endpoint
                    if cmd_str.startswith("stdio:"):
                        cmd_str = cmd_str[len("stdio:"):].strip()
                    parts = shlex.split(cmd_str)
                    if parts:
                        mcp_server_configs.append(
                            types.McpStdioServer(
                                name=name,
                                command=parts[0],
                                args=parts[1:] if len(parts) > 1 else [],
                            )
                        )

        response_schema = (
            IncidentDossier if config.structured_output else None
        )

        if config.local_url:
            return LocalOpenAIAgentConfig(
                base_url=config.local_url,
                model=config.local_model or "gemma2:9b",
                system_instructions=system_prompt,
                tools=tools if tools else None,
                capabilities=capabilities,
                policies=policies,
                retry_config=retry_config,
                compaction_config=compaction_config,
                mcp_servers=mcp_server_configs if mcp_server_configs else None,
                response_schema=response_schema,
                app_data_dir=app_data_dir,
                workspaces=[str(config.code_root.resolve())],
            )

        is_vertex = config.vertex or bool(config.project)
        return LocalAgentConfig(
            system_instructions=system_prompt,
            model=config.model,
            tools=tools if tools else None,
            capabilities=capabilities,
            policies=policies,
            retry_config=retry_config,
            budget_config=budget_config,
            compaction_config=compaction_config,
            mcp_servers=mcp_server_configs if mcp_server_configs else None,
            response_schema=response_schema,
            app_data_dir=app_data_dir,
            workspaces=[str(config.code_root.resolve())],
            api_key=config.api_key,
            vertex=True if is_vertex else None,
            project=config.project,
            location=config.location,
        )
