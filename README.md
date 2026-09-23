# LogNarrator

<p align="center">
  <strong>Real-time log translator, diagnostic copilot, and incident narrator.</strong><br>
  Powered by the <strong>Google Antigravity SDK</strong> and <strong>Gemini</strong>.
</p>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python" alt="Python 3.10+"/></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"/></a>
  <a href="https://pydantic.dev"><img src="https://img.shields.io/badge/pydantic-v2-e92063?logo=pydantic" alt="Pydantic v2"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"/></a>
</p>

<p align="center">
  <img src="assets/demo2.svg?v=2" alt="LogNarrator Live Split-Screen TUI" width="100%" />
</p>

---

## Overview

LogNarrator intercepts raw log streams from standard input or disk, drops routine heartbeat noise, debounces rapid error bursts into unified incident clusters, inspects local source code around stack traces, and streams plain-language operational narratives and incident postmortems directly to your terminal.

---

## Installation

### Prerequisites
- Python 3.10 or higher (Python 3.12 recommended)

### 1. Clone the Repository
```bash
git clone https://github.com/AndrewMason7/LogNarrator.git
cd LogNarrator
```

### 2. Install Dependencies

Install LogNarrator and its required dependencies using `uv` (recommended) or `pip`:

**Option A: uv (High-speed — recommended)**
```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Option B: Standard pip (Built into Python)**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Configure Authentication
Copy the sample environment file:
```bash
cp .env.example .env
```

Select one of the following authentication modes in `.env`:

- **Gemini Developer API (API Key)**:
  ```ini
  GEMINI_API_KEY=your_api_key_here
  ```
- **Google Cloud Vertex AI (Standard Mode ADC)**:
  ```bash
  gcloud auth application-default login
  ```
  ```ini
  LOG_NARRATOR_VERTEX=true
  GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  ```
- **Local / Offline (Ollama, vLLM, LM Studio)**:
  ```ini
  LOCAL_MODEL_URL=http://localhost:11434/v1
  LOCAL_MODEL_NAME=gemma2:9b
  ```

### 2. Run LogNarrator

With your virtual environment active, run `log-narrator` directly:

```bash
# Pipe any live log stream
tail -f /var/log/app.log | log-narrator

# Or tail a file directly
log-narrator -f /var/log/app.log
```
*(Or run without manual activation: `uv run log-narrator`).*

---

## Core Capabilities

- **Automated Source Inspection**: When a stack trace is encountered (e.g. `services/payment.py:142`), LogNarrator safely inspects the surrounding lines in your local repository to identify root causes in context.
- **Live Thought Streaming**: Renders intermediate model reasoning tokens in real time, exposing the agent's diagnostic steps before the final narrative is written.
- **Noise Filtering & Burst Debouncing**: In-memory preprocessors strip routine health checks (`/healthz`, `heartbeat`) and cluster cascading error spikes to prevent redundant model calls.
- **Rolling Context Compaction**: Automatically compacts older conversation turns once token thresholds are reached, maintaining low latency during continuous tailing sessions.
- **Postmortems & Structured JSON**: Exports Markdown incident reports upon exit (`Ctrl+C`) or emits schema-validated Pydantic JSON (`IncidentDossier`) for alerting pipelines.
- **Model Context Protocol (MCP)**: Attach external diagnostic tools (Kubernetes, AWS, databases) dynamically via stdio or SSE endpoints.

---

## Common Usage Recipes

### Pipe Logs from Stdin
```bash
# Docker container logs
docker logs -f backend_api | log-narrator

# Historical crash log analysis
cat server_crash.log | log-narrator --sink stdout
```

### Tail Files on Disk
```bash
# Handles file truncation and logrotate inode rotation automatically
log-narrator -f /var/log/app.log
```

### Enable Source Code Inspection
```bash
# Point to your local codebase root
log-narrator -f ./app.log -c /path/to/my_repo
```

### Export Incident Postmortems
```bash
# Generates a Markdown postmortem report upon exit (Ctrl+C)
log-narrator -f ./app.log -e ./incident_report.md
```

### Schema-Validated JSON Output
```bash
# Emits Pydantic IncidentDossier JSON to stdout for automation
log-narrator -f ./app.log --structured-output --sink stdout
```

### Connect External MCP Tool Servers
```bash
# Attach Kubernetes or APM tools
log-narrator -f ./app.log -M k8s=http://localhost:9090/sse
```

---

## CLI Reference

```
Usage: log-narrator [OPTIONS]

Options:
  -f, --file PATH                 File path to tail continuously.
  -s, --sink [rich_tui|stdout]    Output presentation sink (default: rich_tui).
  -m, --mode [diagnostic|concise] Narrative response mode (default: diagnostic).
  -l, --lang TEXT                 Target output language (default: English).
  -d, --debounce FLOAT            Debounce interval in seconds (default: 1.5).
  -c, --code-root PATH            Root directory for code inspection (default: .).
  -e, --export-markdown PATH      Markdown postmortem export file path.
  --model TEXT                    Model identifier (e.g. gemini-2.5-flash).
  --api-key TEXT                  Gemini API Key (or set GEMINI_API_KEY).
  --vertex                        Use Gemini Enterprise Platform (Vertex AI).
  --project TEXT                  Google Cloud project ID for Vertex AI (ADC).
  --location TEXT                 Google Cloud region (e.g. us-central1).
  --local-url TEXT                Local OpenAI-compatible URL (e.g. http://localhost:11434/v1).
  --local-model TEXT              Model name for local server (default: gemma2:9b).
  --structured-output             Enforce schema-validated structured JSON output.
  -M, --mcp-server TEXT           Attach MCP server (format: name=url or name=command).
  --compaction-token-threshold N  Token count threshold for rolling context compaction.
  --max-retries INTEGER           Maximum API retries for transient failures (default: 3).
  --max-total-tokens INTEGER      Budget ceiling: maximum session tokens.
  --max-model-calls INTEGER       Budget ceiling: maximum model calls.
  --app-data-dir PATH             Custom application data directory for artifacts.
  --debug                         Enable verbose SDK and pipeline debug logging.
  --help                          Show this message and exit.
```

---

## Programmatic Python SDK Usage

Embed LogNarrator directly into Python applications:

```python
import asyncio
from log_narrator.config import NarratorConfig
from log_narrator.coordinator import PipelineCoordinator
from log_narrator.ingestion.file_tailer import FileTailer
from log_narrator.sinks.stdout_sink import StdoutSink

async def main():
    # Configure via convenience factory
    config = NarratorConfig.for_vertex(
        project="my-gcp-project",
        location="us-central1",
        mode="diagnostic",
        sink="stdout",
        debounce_seconds=1.0,
    )

    reader = FileTailer("./app.log", from_beginning=True)
    coordinator = PipelineCoordinator(
        config=config,
        reader=reader,
        sink=StdoutSink(),
    )

    postmortem_path = await coordinator.run()
    if postmortem_path:
        print(f"Incident postmortem exported to: {postmortem_path}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Project Structure

```
src/log_narrator/
├── agent/              # Google Antigravity SDK integration
│   ├── core.py         # Agent runtime lifecycle, streaming, and tool execution
│   ├── factory.py      # SDK configuration assembly (Vertex, Gemini, Local, MCP)
│   ├── prompts.py      # System instructions and prompt construction
│   └── tools.py        # Sandboxed source inspection tools
├── engine/             # Stream processing and analysis
│   ├── buffer.py       # Time-windowed burst debouncing
│   ├── incident_extractor.py # Multilingual crash signature extractor
│   ├── models.py       # Pydantic data models (LogLine, LogBatch, IncidentDossier)
│   └── preprocessor.py # Regex noise filtering
├── ingestion/          # Log source readers
│   ├── base.py         # Abstract log reader interface
│   ├── file_tailer.py  # Non-blocking file tailer with logrotate handling
│   └── stdin_reader.py # Asynchronous stdin stream reader
├── recorder/           # Postmortem generation
│   └── postmortem.py   # Incident timeline and Markdown report recorder
├── sinks/              # Output presentation layers
│   ├── base.py         # Abstract output sink interface
│   ├── rich_tui.py     # Split-screen live terminal dashboard
│   └── stdout_sink.py  # Headless streamable stdout sink
├── cli.py              # Click command-line interface
├── config.py           # Unified settings facade and domain sub-models
├── coordinator.py      # Async dataflow pipeline coordinator
└── __main__.py         # Package execution entrypoint
```

---

## Dependencies

### Core Runtime
| Package | Version | Purpose |
| :--- | :--- | :--- |
| [`google-antigravity`](https://pypi.org/project/google-antigravity/) | `>=0.1.18` | Agent orchestration, thought streaming, context compaction, and MCP tool execution |
| [`pydantic`](https://pydantic.dev/) | `>=2.7.0` | Strongly-typed data schemas and incident dossier validation (`IncidentDossier`) |
| [`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | `>=2.2.0` | Unified configuration loading across `.env`, CLI flags, and GCP environment variables |
| [`rich`](https://rich.readthedocs.io/) | `>=13.7.0` | Split-screen terminal dashboard (`rich_tui`), markdown rendering, and thought panels |
| [`click`](https://click.palletsprojects.com/) | `>=8.1.0` | CLI option parsing and sub-command routing |
| [`aiofiles`](https://github.com/Tinche/aiofiles) | `>=23.2.0` | Non-blocking asynchronous file tailing and log I/O |

### Development & Testing
| Package | Version | Purpose |
| :--- | :--- | :--- |
| [`pytest`](https://docs.pytest.org/) | `>=8.0.0` | Test runner and assertion framework |
| [`pytest-asyncio`](https://pytest-asyncio.readthedocs.io/) | `>=0.23.0` | Async test fixtures and event loop management |
| [`ruff`](https://docs.astral-sh.io/ruff/) | `latest` | High-speed linting and code formatting |

---

## Testing

LogNarrator maintains a comprehensive, deterministic test suite with zero artificial sleep delays:

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=log_narrator --cov-report=term-missing

# Run linter
uv run ruff check .
```

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
