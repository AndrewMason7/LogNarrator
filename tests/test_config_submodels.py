from log_narrator.config import (
    ModelConfig,
    NarratorConfig,
    PipelineConfig,
    TuningConfig,
)


def test_config_submodels_isolation():
    model_cfg = ModelConfig(local_url="http://localhost:11434/v1", local_model="llama3")
    assert model_cfg.local_url == "http://localhost:11434/v1"
    assert model_cfg.local_model == "llama3"
    assert model_cfg.is_local is True
    assert model_cfg.is_vertex is False

    pipe_cfg = PipelineConfig(debounce_seconds=2.0, max_batch_lines=100)
    assert pipe_cfg.debounce_seconds == 2.0
    assert pipe_cfg.max_batch_lines == 100

    tuning_cfg = TuningConfig(compaction_token_threshold=50000, max_retries=5)
    assert tuning_cfg.compaction_token_threshold == 50000
    assert tuning_cfg.max_retries == 5

def test_narrator_config_backward_compatibility():
    config = NarratorConfig(
        local_url="http://localhost:11434/v1",
        debounce_seconds=2.5,
        compaction_token_threshold=30000,
        _env_file=None,
    )
    # Direct access on facade
    assert config.local_url == "http://localhost:11434/v1"
    assert config.debounce_seconds == 2.5
    assert config.compaction_token_threshold == 30000
    assert config.is_local is True
    assert config.is_vertex is False

    # Grouped sub-models accessible
    assert config.model_settings.local_url == "http://localhost:11434/v1"
    assert config.pipeline_settings.debounce_seconds == 2.5
    assert config.tuning_settings.compaction_token_threshold == 30000

def test_narrator_config_convenience_factories():
    # Local model factory
    local_cfg = NarratorConfig.for_local(
        local_url="http://localhost:11434/v1",
        local_model="mistral:7b",
        debounce_seconds=3.0,
    )
    assert local_cfg.is_local is True
    assert local_cfg.local_url == "http://localhost:11434/v1"
    assert local_cfg.local_model == "mistral:7b"
    assert local_cfg.debounce_seconds == 3.0

    # Vertex AI factory
    vertex_cfg = NarratorConfig.for_vertex(
        project="prod-gcp-1",
        location="us-central1",
        model="gemini-2.5-flash",
    )
    assert vertex_cfg.is_vertex is True
    assert vertex_cfg.vertex is True
    assert vertex_cfg.project == "prod-gcp-1"
    assert vertex_cfg.location == "us-central1"
    assert vertex_cfg.model == "gemini-2.5-flash"

    # Gemini API factory
    gemini_cfg = NarratorConfig.for_gemini(
        api_key="ai-key-xyz",
        model="gemini-2.5-pro",
    )
    assert gemini_cfg.api_key == "ai-key-xyz"
    assert gemini_cfg.model == "gemini-2.5-pro"

    # Composition from sub-settings
    composed_cfg = NarratorConfig.from_settings(
        pipeline=PipelineConfig(debounce_seconds=0.8),
        model=ModelConfig(model="gemini-2.5-flash"),
        tuning=TuningConfig(max_retries=5),
        target_language="French",
    )
    assert composed_cfg.debounce_seconds == 0.8
    assert composed_cfg.model == "gemini-2.5-flash"
    assert composed_cfg.max_retries == 5
    assert composed_cfg.target_language == "French"


def test_single_local_model_default():
    config = NarratorConfig()
    assert config.local_model == "gemma2:9b"
    assert config.model_settings.local_model == "gemma2:9b"


def test_composed_submodel_updates_reflected():
    model_cfg = ModelConfig(local_url="http://localhost:11434/v1", local_model="gemma2:9b")
    config = NarratorConfig.from_settings(model=model_cfg)
    assert config.is_local is True
    assert config.local_model == "gemma2:9b"

