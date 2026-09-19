from pathlib import Path

from log_narrator.config import NarratorConfig
from log_narrator.engine.models import LogBatch, LogLine


def test_default_config():
    config = NarratorConfig()
    assert config.mode == "diagnostic"
    assert config.target_language == "English"
    assert config.debounce_seconds == 1.5
    assert config.max_batch_lines == 50
    assert config.sink == "rich_tui"
    assert config.model is None

def test_custom_config_override():
    config = NarratorConfig(
        mode="concise",
        target_language="Spanish",
        debounce_seconds=0.5,
        sink="stdout",
        model="custom-model",
    )
    assert config.mode == "concise"
    assert config.target_language == "Spanish"
    assert config.debounce_seconds == 0.5
    assert config.sink == "stdout"
    assert config.model == "custom-model"

def test_log_batch_assembly():
    lines = [
        LogLine(content="Error: connection refused", line_number=1),
        LogLine(content="Traceback (most recent call last):", line_number=2),
    ]
    batch = LogBatch(lines=lines, source="stdin")
    assert batch.total_lines == 2
    assert "connection refused" in batch.raw_text


def test_env_file_loading(tmp_path: Path, monkeypatch):
    # Clear any host environment variables to test pure .env parsing
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LOG_NARRATOR_API_KEY", raising=False)
    monkeypatch.delenv("LOG_NARRATOR_MODE", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=sk-antigravity-12345\nLOG_NARRATOR_MODE=concise\n")
    monkeypatch.chdir(tmp_path)

    config = NarratorConfig(_env_file=str(env_file))
    assert config.api_key == "sk-antigravity-12345"
    assert config.mode == "concise"


def test_standard_mode_config():
    config = NarratorConfig(project="my-gcp-project", location="us-central1")
    assert config.project == "my-gcp-project"
    assert config.location == "us-central1"


def test_standard_mode_env_aliases(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcp-prod-1")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")

    config = NarratorConfig()
    assert config.project == "gcp-prod-1"
    assert config.location == "europe-west1"


