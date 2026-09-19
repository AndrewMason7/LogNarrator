from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

# =====================================================================
# 1. Type Aliases & Constants
# =====================================================================

ResponseMode = Literal["diagnostic", "concise"]
OutputSinkType = Literal["rich_tui", "stdout"]

DEFAULT_IGNORED_PATTERNS: list[str] = [
    r"GET\s+/health\s+200",
    r"GET\s+/healthz\s+200",
    r"GET\s+/livez\s+200",
    r"ping\s+pong",
    r"heartbeat\s+ok",
    r"Keep-Alive\s+ping",
]


# =====================================================================
# 2. Cohesive Sub-Domain Models
# =====================================================================

class PipelineConfig(BaseModel):
    """Configuration for log ingestion, buffering, pacing, and output sinks."""

    mode: ResponseMode = Field(
        default="diagnostic",
        description="Narrative response mode: diagnostic or concise.",
    )
    target_language: str = Field(
        default="English",
        description="Target human language for narrative outputs.",
    )
    code_root: Path = Field(
        default_factory=Path.cwd,
        description="Root directory for local source code inspection.",
    )
    debounce_seconds: float = Field(
        default=1.5,
        description="Pacing debounce interval in seconds before flushing a log batch.",
    )
    max_batch_lines: int = Field(
        default=50,
        description="Maximum number of log lines allowed in a single processing batch.",
    )
    sink: OutputSinkType = Field(
        default="rich_tui",
        description="Presentation sink for logs and diagnostics.",
    )
    export_markdown: Path | None = Field(
        default=None,
        description="Optional path to export postmortem Markdown report upon exit.",
    )
    ignored_patterns: list[str] = Field(
        default=DEFAULT_IGNORED_PATTERNS,
        description="Regex patterns to filter noisy heartbeat logs.",
    )
    inspect_code: bool = Field(
        default=True,
        description="Enable automated source code inspection for stack traces.",
    )


class ModelConfig(BaseModel):
    """Configuration for AI model providers (Gemini Developer API, Vertex AI, or Local OpenAI)."""

    model: str | None = Field(
        default=None,
        description="Model identifier (e.g. gemini-2.5-flash, gemma2:9b).",
    )
    api_key: str | None = Field(
        default=None,
        description="Gemini Developer API key.",
    )
    vertex: bool = Field(
        default=False,
        description="Enable Google Cloud Vertex AI standard mode.",
    )
    project: str | None = Field(
        default=None,
        description="Google Cloud project ID for Vertex AI ADC.",
    )
    location: str | None = Field(
        default=None,
        description="Google Cloud region for Vertex AI ADC (e.g. us-central1).",
    )
    local_url: str | None = Field(
        default=None,
        description="Local OpenAI-compatible base URL (e.g. http://localhost:11434/v1).",
    )
    local_model: str = Field(
        default="gemma2:9b",
        description="Model name for local OpenAI-compatible endpoint.",
    )

    @property
    def is_local(self) -> bool:
        """Returns True if targeting a local OpenAI-compatible endpoint (Ollama/vLLM/LM Studio)."""
        return bool(self.local_url)

    @property
    def is_vertex(self) -> bool:
        """Returns True if targeting Google Cloud Vertex AI via ADC."""
        return self.vertex or bool(self.project)


class TuningConfig(BaseModel):
    """Configuration for SDK retry resilience, token budgets, context compaction, and MCP tools."""

    debug: bool = Field(
        default=False,
        description="Enable verbose Antigravity SDK and pipeline debug logging.",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum API retries for transient failures with exponential backoff.",
    )
    app_data_dir: Path | None = Field(
        default=None,
        description="Custom application data directory for agent state and artifacts.",
    )
    max_model_calls: int | None = Field(
        default=None,
        description="Budget guardrail: maximum model calls allowed in session.",
    )
    max_total_tokens: int | None = Field(
        default=None,
        description="Budget guardrail: maximum total tokens allowed in session.",
    )
    compaction_token_threshold: int | None = Field(
        default=None,
        description="Token threshold triggering automatic rolling context compaction.",
    )
    mcp_servers: list[str] = Field(
        default_factory=list,
        description="External MCP servers in name=url or name=command format.",
    )
    structured_output: bool = Field(
        default=False,
        description="Enforce schema-validated structured output (IncidentDossier).",
    )


# =====================================================================
# 3. Internal Environment Variable Loader
# =====================================================================

class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LOG_NARRATOR_",
        extra="ignore",
    )

    mode: ResponseMode = "diagnostic"
    target_language: str = "English"
    code_root: Path = Field(default_factory=Path.cwd)
    debounce_seconds: float = 1.5
    max_batch_lines: int = 50
    sink: OutputSinkType = "rich_tui"
    export_markdown: Path | None = None
    ignored_patterns: list[str] = DEFAULT_IGNORED_PATTERNS
    inspect_code: bool = True

    model: str | None = None
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "LOG_NARRATOR_API_KEY", "api_key"),
    )
    vertex: bool = False
    project: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT", "LOG_NARRATOR_PROJECT", "project"
        ),
    )
    location: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GOOGLE_CLOUD_LOCATION", "GCP_LOCATION", "LOG_NARRATOR_LOCATION", "location"
        ),
    )
    local_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOCAL_MODEL_URL", "OLLAMA_HOST", "local_url"),
    )
    local_model: str = Field(
        default="gemma2:9b",
        validation_alias=AliasChoices("LOCAL_MODEL_NAME", "local_model"),
    )

    debug: bool = False
    max_retries: int = 3
    app_data_dir: Path | None = None
    max_model_calls: int | None = None
    max_total_tokens: int | None = None
    compaction_token_threshold: int | None = None
    mcp_servers: list[str] = Field(default_factory=list)
    structured_output: bool = False


# =====================================================================
# 4. Unified Settings Facade (Submodel Composition)
# =====================================================================

class NarratorConfig(BaseSettings):
    """Unified configuration facade composing pipeline, model, and tuning settings.

    Supports configuration via:
    - Direct keyword arguments
    - Composed submodel objects (PipelineConfig, ModelConfig, TuningConfig)
    - Environment variables (LOG_NARRATOR_* or canonical aliases like GEMINI_API_KEY)
    - Dotenv files (.env)
    - Domain factory methods (.for_local(), .for_vertex(), .for_gemini(), .from_settings())
    """

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
    )

    _pipeline: PipelineConfig = PrivateAttr()
    _model: ModelConfig = PrivateAttr()
    _tuning: TuningConfig = PrivateAttr()

    def __init__(
        self,
        pipeline: PipelineConfig | None = None,
        model: ModelConfig | str | None = None,
        tuning: TuningConfig | None = None,
        _env_file: str | Path | None = ".env",
        **kwargs: Any,
    ) -> None:
        super().__init__()
        raw_kwargs = dict(kwargs)
        if isinstance(model, str):
            raw_kwargs["model"] = model
            model_obj = None
        else:
            model_obj = model

        loader_kwargs = dict(raw_kwargs)
        loader_kwargs["_env_file"] = _env_file

        env_loader = _EnvSettings(**loader_kwargs)

        p_fields = set(PipelineConfig.model_fields.keys())
        m_fields = set(ModelConfig.model_fields.keys())
        t_fields = set(TuningConfig.model_fields.keys())

        if pipeline is not None:
            p_obj = pipeline.model_copy(deep=True)
            for k, v in raw_kwargs.items():
                if k in p_fields:
                    setattr(p_obj, k, v)
        else:
            p_dict = {f: raw_kwargs[f] if f in raw_kwargs else getattr(env_loader, f) for f in p_fields}
            p_obj = PipelineConfig(**p_dict)

        if model_obj is not None:
            m_obj = model_obj.model_copy(deep=True)
            for k, v in raw_kwargs.items():
                if k in m_fields:
                    setattr(m_obj, k, v)
        else:
            m_dict = {f: raw_kwargs[f] if f in raw_kwargs else getattr(env_loader, f) for f in m_fields}
            m_obj = ModelConfig(**m_dict)

        if tuning is not None:
            t_obj = tuning.model_copy(deep=True)
            for k, v in raw_kwargs.items():
                if k in t_fields:
                    setattr(t_obj, k, v)
        else:
            t_dict = {f: raw_kwargs[f] if f in raw_kwargs else getattr(env_loader, f) for f in t_fields}
            t_obj = TuningConfig(**t_dict)

        self._pipeline = p_obj
        self._model = m_obj
        self._tuning = t_obj

    # -----------------------------------------------------------------
    # Sub-Model Accessors
    # -----------------------------------------------------------------
    @property
    def pipeline_settings(self) -> PipelineConfig:
        return self._pipeline

    @property
    def model_settings(self) -> ModelConfig:
        return self._model

    @property
    def tuning_settings(self) -> TuningConfig:
        return self._tuning

    # -----------------------------------------------------------------
    # Pipeline Delegations
    # -----------------------------------------------------------------
    @property
    def mode(self) -> ResponseMode:
        return self._pipeline.mode

    @mode.setter
    def mode(self, val: ResponseMode) -> None:
        self._pipeline.mode = val

    @property
    def target_language(self) -> str:
        return self._pipeline.target_language

    @target_language.setter
    def target_language(self, val: str) -> None:
        self._pipeline.target_language = val

    @property
    def code_root(self) -> Path:
        return self._pipeline.code_root

    @code_root.setter
    def code_root(self, val: Path) -> None:
        self._pipeline.code_root = val

    @property
    def debounce_seconds(self) -> float:
        return self._pipeline.debounce_seconds

    @debounce_seconds.setter
    def debounce_seconds(self, val: float) -> None:
        self._pipeline.debounce_seconds = val

    @property
    def max_batch_lines(self) -> int:
        return self._pipeline.max_batch_lines

    @max_batch_lines.setter
    def max_batch_lines(self, val: int) -> None:
        self._pipeline.max_batch_lines = val

    @property
    def sink(self) -> OutputSinkType:
        return self._pipeline.sink

    @sink.setter
    def sink(self, val: OutputSinkType) -> None:
        self._pipeline.sink = val

    @property
    def export_markdown(self) -> Path | None:
        return self._pipeline.export_markdown

    @export_markdown.setter
    def export_markdown(self, val: Path | None) -> None:
        self._pipeline.export_markdown = val

    @property
    def ignored_patterns(self) -> list[str]:
        return self._pipeline.ignored_patterns

    @ignored_patterns.setter
    def ignored_patterns(self, val: list[str]) -> None:
        self._pipeline.ignored_patterns = val

    @property
    def inspect_code(self) -> bool:
        return self._pipeline.inspect_code

    @inspect_code.setter
    def inspect_code(self, val: bool) -> None:
        self._pipeline.inspect_code = val

    # -----------------------------------------------------------------
    # Model Delegations
    # -----------------------------------------------------------------
    @property
    def model(self) -> str | None:
        return self._model.model

    @model.setter
    def model(self, val: str | None) -> None:
        self._model.model = val

    @property
    def api_key(self) -> str | None:
        return self._model.api_key

    @api_key.setter
    def api_key(self, val: str | None) -> None:
        self._model.api_key = val

    @property
    def vertex(self) -> bool:
        return self._model.vertex

    @vertex.setter
    def vertex(self, val: bool) -> None:
        self._model.vertex = val

    @property
    def project(self) -> str | None:
        return self._model.project

    @project.setter
    def project(self, val: str | None) -> None:
        self._model.project = val

    @property
    def location(self) -> str | None:
        return self._model.location

    @location.setter
    def location(self, val: str | None) -> None:
        self._model.location = val

    @property
    def local_url(self) -> str | None:
        return self._model.local_url

    @local_url.setter
    def local_url(self, val: str | None) -> None:
        self._model.local_url = val

    @property
    def local_model(self) -> str:
        return self._model.local_model

    @local_model.setter
    def local_model(self, val: str) -> None:
        self._model.local_model = val

    @property
    def is_local(self) -> bool:
        return self._model.is_local

    @property
    def is_vertex(self) -> bool:
        return self._model.is_vertex

    # -----------------------------------------------------------------
    # Tuning Delegations
    # -----------------------------------------------------------------
    @property
    def debug(self) -> bool:
        return self._tuning.debug

    @debug.setter
    def debug(self, val: bool) -> None:
        self._tuning.debug = val

    @property
    def max_retries(self) -> int:
        return self._tuning.max_retries

    @max_retries.setter
    def max_retries(self, val: int) -> None:
        self._tuning.max_retries = val

    @property
    def app_data_dir(self) -> Path | None:
        return self._tuning.app_data_dir

    @app_data_dir.setter
    def app_data_dir(self, val: Path | None) -> None:
        self._tuning.app_data_dir = val

    @property
    def max_model_calls(self) -> int | None:
        return self._tuning.max_model_calls

    @max_model_calls.setter
    def max_model_calls(self, val: int | None) -> None:
        self._tuning.max_model_calls = val

    @property
    def max_total_tokens(self) -> int | None:
        return self._tuning.max_total_tokens

    @max_total_tokens.setter
    def max_total_tokens(self, val: int | None) -> None:
        self._tuning.max_total_tokens = val

    @property
    def compaction_token_threshold(self) -> int | None:
        return self._tuning.compaction_token_threshold

    @compaction_token_threshold.setter
    def compaction_token_threshold(self, val: int | None) -> None:
        self._tuning.compaction_token_threshold = val

    @property
    def mcp_servers(self) -> list[str]:
        return self._tuning.mcp_servers

    @mcp_servers.setter
    def mcp_servers(self, val: list[str]) -> None:
        self._tuning.mcp_servers = val

    @property
    def structured_output(self) -> bool:
        return self._tuning.structured_output

    @structured_output.setter
    def structured_output(self, val: bool) -> None:
        self._tuning.structured_output = val

    # -----------------------------------------------------------------
    # Factory Methods
    # -----------------------------------------------------------------
    @classmethod
    def from_settings(
        cls,
        pipeline: PipelineConfig | None = None,
        model: ModelConfig | None = None,
        tuning: TuningConfig | None = None,
        **overrides: Any,
    ) -> "NarratorConfig":
        """Constructs a NarratorConfig by composing sub-domain configurations."""
        return cls(pipeline=pipeline, model=model, tuning=tuning, **overrides)

    @classmethod
    def for_local(
        cls,
        local_url: str = "http://localhost:11434/v1",
        local_model: str = "gemma2:9b",
        **kwargs: Any,
    ) -> "NarratorConfig":
        """Convenience factory for offline/air-gapped local model inference."""
        return cls(local_url=local_url, local_model=local_model, **kwargs)

    @classmethod
    def for_vertex(
        cls,
        project: str,
        location: str = "us-central1",
        model: str | None = None,
        **kwargs: Any,
    ) -> "NarratorConfig":
        """Convenience factory for Google Cloud Vertex AI (Standard Mode ADC)."""
        return cls(vertex=True, project=project, location=location, model=model, **kwargs)

    @classmethod
    def for_gemini(
        cls,
        api_key: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> "NarratorConfig":
        """Convenience factory for Google Gemini Developer API."""
        return cls(api_key=api_key, model=model, **kwargs)

    # -----------------------------------------------------------------
    # Serialization and Representation
    # -----------------------------------------------------------------
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Returns a flat dictionary containing all composed configuration values."""
        res: dict[str, Any] = {}
        res.update(self._pipeline.model_dump(*args, **kwargs))
        res.update(self._model.model_dump(*args, **kwargs))
        res.update(self._tuning.model_dump(*args, **kwargs))
        return res

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        """Returns a JSON string containing all composed configuration values."""
        import json
        return json.dumps(self.model_dump(*args, **kwargs), default=str)

    def __repr__(self) -> str:
        return (
            f"NarratorConfig(pipeline={self._pipeline!r}, "
            f"model={self._model!r}, tuning={self._tuning!r})"
        )
