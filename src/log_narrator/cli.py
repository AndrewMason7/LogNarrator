import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from log_narrator.config import NarratorConfig
from log_narrator.coordinator import PipelineCoordinator
from log_narrator.ingestion.file_tailer import FileTailer
from log_narrator.ingestion.stdin_reader import StdinReader


def pipeline_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for log ingestion, buffering, and presentation sink options."""
    f = click.option("--file", "-f", type=click.Path(path_type=Path), default=None, help="File path to tail continuously.")(f)
    f = click.option("--mode", "-m", type=click.Choice(["diagnostic", "concise"]), default="diagnostic", help="Narrative response mode.")(f)
    f = click.option("--lang", "-l", default="English", help="Target output language.")(f)
    f = click.option("--code-root", "-c", type=click.Path(path_type=Path), default=Path.cwd(), help="Root directory for source code inspection.")(f)
    f = click.option("--debounce", "-d", type=float, default=1.5, help="Debounce interval in seconds.")(f)
    f = click.option("--sink", "-s", type=click.Choice(["rich_tui", "stdout"]), default="rich_tui", help="Output presentation sink.")(f)
    f = click.option("--export-markdown", "-e", type=click.Path(path_type=Path), default=None, help="Markdown postmortem export file path.")(f)
    return f

def model_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for AI model provider options (Gemini Cloud vs Local OpenAI)."""
    f = click.option("--model", default=None, help="Gemini model identifier (defaults to SDK built-in default).")(f)
    f = click.option("--api-key", envvar="GEMINI_API_KEY", default=None, help="Gemini API Key (or set GEMINI_API_KEY env var).")(f)
    f = click.option("--vertex", is_flag=True, default=False, help="Use Gemini Enterprise Agent Platform (Vertex AI).")(f)
    f = click.option("--project", envvar="GOOGLE_CLOUD_PROJECT", default=None, help="Google Cloud project ID for Standard Mode (ADC).")(f)
    f = click.option("--location", envvar="GOOGLE_CLOUD_LOCATION", default=None, help="Google Cloud location/region (e.g. us-central1).")(f)
    f = click.option("--local-url", default=None, help="Local OpenAI-compatible base URL (e.g. http://localhost:11434/v1 for Ollama).")(f)
    f = click.option("--local-model", default="gemma2:9b", help="Model name for local server (e.g. gemma2:9b, llama3).")(f)
    return f

def tuning_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for SDK retry, budget limits, compaction, and MCP options."""
    f = click.option("--debug", is_flag=True, default=False, help="Enable verbose SDK and pipeline debug logging.")(f)
    f = click.option("--max-retries", type=int, default=3, help="Maximum API retries for transient failures.")(f)
    f = click.option("--app-data-dir", type=click.Path(path_type=Path), default=None, help="Custom application data directory for artifacts.")(f)
    f = click.option("--max-model-calls", type=int, default=None, help="Budget limit: maximum model calls.")(f)
    f = click.option("--max-total-tokens", type=int, default=None, help="Budget limit: maximum total tokens.")(f)
    f = click.option("--compaction-token-threshold", type=int, default=None, help="Token count threshold to trigger automatic context compaction.")(f)
    f = click.option("--mcp-server", "-M", "mcp_servers", multiple=True, help="MCP server in format name=url or name=command (e.g. k8s=http://localhost:9090/sse).")(f)
    f = click.option("--structured-output", is_flag=True, default=False, help="Enforce schema-validated structured JSON output.")(f)
    return f

@click.command()
@pipeline_options
@model_options
@tuning_options
def main(**kwargs: Any) -> None:
    """LogNarrator: Autonomous real-time log translator, diagnostic copilot, and incident narrator."""
    file = kwargs.pop("file", None)
    debug = kwargs.get("debug", False)
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("google.antigravity").setLevel(logging.DEBUG)

    if "mcp_servers" in kwargs:
        kwargs["mcp_servers"] = list(kwargs["mcp_servers"])
    if "lang" in kwargs:
        kwargs["target_language"] = kwargs.pop("lang")
    if "debounce" in kwargs:
        kwargs["debounce_seconds"] = kwargs.pop("debounce")

    config = NarratorConfig(**kwargs)
    reader = FileTailer(file, from_beginning=False) if file else StdinReader()
    coordinator = PipelineCoordinator(config=config, reader=reader)

    try:
        saved_report = asyncio.run(coordinator.run())
        if saved_report:
            print(f"\n[LogNarrator] Postmortem exported to {saved_report}")
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

