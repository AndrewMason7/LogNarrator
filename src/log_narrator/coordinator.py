import asyncio
import logging
import random
import time
from pathlib import Path

from google.antigravity.types import AntigravityCancelledError

from log_narrator.agent.core import RATE_LIMIT_PATTERN, AgentDiagnosticCore
from log_narrator.config import NarratorConfig
from log_narrator.engine.buffer import LogBuffer
from log_narrator.engine.incident_extractor import IncidentExtractor
from log_narrator.engine.models import IncidentEvent, LogBatch
from log_narrator.engine.preprocessor import LogPreprocessor
from log_narrator.ingestion.base import BaseLogReader
from log_narrator.ingestion.stdin_reader import StdinReader
from log_narrator.recorder.postmortem import IncidentRecorder
from log_narrator.sinks.base import BaseOutputSink
from log_narrator.sinks.rich_tui import RichTUIOutputSink
from log_narrator.sinks.stdout_sink import StdoutSink

logger = logging.getLogger(__name__)

SINK_REGISTRY: dict[str, type[BaseOutputSink]] = {
    "rich_tui": RichTUIOutputSink,
    "stdout": StdoutSink,
}

class PipelineCoordinator:
    """Coordinates log ingestion, buffering, AI diagnostics, output presentation, and postmortem export."""

    def __init__(
        self,
        config: NarratorConfig,
        reader: BaseLogReader | None = None,
        sink: BaseOutputSink | None = None,
        agent_core: AgentDiagnosticCore | None = None,
        recorder: IncidentRecorder | None = None,
        extractor: IncidentExtractor | None = None,
    ) -> None:
        self.config = config
        self.sink = sink or self._create_sink(config.sink)
        self.reader = reader or StdinReader()
        self.agent_core = agent_core or AgentDiagnosticCore(config)
        self.recorder = recorder or IncidentRecorder(export_path=config.export_markdown)
        self.extractor = extractor or IncidentExtractor()

        preprocessor = LogPreprocessor(config.ignored_patterns)
        self.buffer = LogBuffer(
            preprocessor=preprocessor,
            debounce_seconds=config.debounce_seconds,
            max_batch_lines=config.max_batch_lines,
        )
        self._turn_count: int = 0
        self._last_turn_time: float = time.monotonic()

    @staticmethod
    def _create_sink(sink_type: str) -> BaseOutputSink:
        if sink_type not in SINK_REGISTRY:
            valid = ", ".join(repr(k) for k in sorted(SINK_REGISTRY))
            raise ValueError(f"Unsupported sink type '{sink_type}'. Valid options: {valid}")
        return SINK_REGISTRY[sink_type]()

    async def run(self) -> Path | None:
        await self.agent_core.start()

        async def ingest_worker() -> None:
            try:
                async for line in self.reader.stream():
                    self.sink.emit_raw_log(line)
                    await self.buffer.push(line)
            finally:
                await self.buffer.close()

        async def process_worker() -> None:
            turn_counter = 0
            while True:
                batch = await self.buffer.get_next_batch()
                if batch is None:
                    break
                turn_counter += 1
                await self._process_turn(turn_counter, batch)

        try:
            await asyncio.gather(ingest_worker(), process_worker())
        except asyncio.CancelledError:
            pass
        finally:
            await self.reader.stop()
            await self.buffer.close()
            usage = (
                self.agent_core.get_total_usage()
                if hasattr(self.agent_core, "get_total_usage")
                else None
            )
            try:
                await asyncio.wait_for(self.agent_core.stop(), timeout=3.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Error stopping agent core: %s", e)
            self.sink.close()

        return self.recorder.export_markdown(usage=usage, turn_count=self._turn_count)

    async def _process_turn(self, turn_id: int, batch: LogBatch) -> None:
        now = time.monotonic()
        if (now - self._last_turn_time) > self.config.idle_reset_seconds:
            if hasattr(self.agent_core, "reset"):
                await self.agent_core.reset()
        self._last_turn_time = now
        self._turn_count = max(self._turn_count, turn_id)
        max_attempts = max(1, self.config.max_retries)

        if self.config.structured_output:
            for attempt in range(max_attempts):
                self.sink.start_turn(turn_id)
                try:
                    dossier = await self.agent_core.diagnose_batch(batch)
                    if dossier:
                        dossier_json = dossier.model_dump_json(indent=2)
                        self.sink.stream_token(dossier_json)
                        headline = getattr(dossier, "headline", getattr(dossier, "summary", "Incident Detected"))
                        actions = getattr(dossier, "recommended_actions", [])
                        remediation = getattr(dossier, "recommended_fix", None) or "\n".join(f"- {a}" for a in actions)
                        affected = getattr(dossier, "affected_components", None) or getattr(dossier, "affected_files", [])
                        inspected = (
                            self.agent_core.pop_inspected_files()
                            if hasattr(self.agent_core, "pop_inspected_files")
                            else []
                        ) or affected
                        incident_id = getattr(dossier, "incident_id", f"INC-{turn_id:03d}")
                        event = IncidentEvent(
                            incident_id=incident_id,
                            headline=headline,
                            raw_log_snippet=batch.raw_text,
                            root_cause=dossier.root_cause,
                            recommended_fix=remediation,
                            inspected_files=inspected,
                        )
                        self.recorder.record(event)
                    self.sink.end_turn()
                    break
                except AntigravityCancelledError:
                    msg = "[Agent Cancelled: Turn was interrupted.]"
                    self.sink.stream_token(msg)
                    self.sink.end_turn()
                    break
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = bool(RATE_LIMIT_PATTERN.search(err_str))
                    if is_rate_limit and attempt < max_attempts - 1:
                        backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                        logger.warning(
                            "Rate limit hit on turn %d (attempt %d/%d): %s. Retrying in %.2fs",
                            turn_id,
                            attempt + 1,
                            max_attempts,
                            err_str,
                            backoff,
                        )
                        self.sink.end_turn()
                        await asyncio.sleep(backoff)
                        continue

                    err_msg = f"[Agent Warning: {err_str}]"
                    self.sink.stream_token(err_msg)
                    self.sink.end_turn()
                    break
        response_parts: list[str] = []
        for attempt in range(max_attempts):
            self.sink.start_turn(turn_id)
            response_parts.clear()
            try:
                if "stream_narrative" in getattr(self.agent_core, "__dict__", {}):
                    async for token in self.agent_core.stream_narrative(batch):
                        response_parts.append(token)
                        self.sink.stream_token(token)
                elif hasattr(self.agent_core, "stream_diagnostic"):
                    async for kind, content in self.agent_core.stream_diagnostic(batch):
                        if kind == "thought":
                            self.sink.stream_thought(content)
                        else:
                            response_parts.append(content)
                            self.sink.stream_token(content)
                else:
                    async for token in self.agent_core.stream_narrative(batch):
                        response_parts.append(token)
                        self.sink.stream_token(token)
                self.sink.end_turn()
                break
            except AntigravityCancelledError:
                msg = "[Agent Cancelled: Turn was interrupted.]"
                self.sink.stream_token(msg)
                response_parts.append(f"\n{msg}")
                self.sink.end_turn()
                break
            except Exception as e:
                err_str = str(e)
                is_rate_limit = bool(RATE_LIMIT_PATTERN.search(err_str))
                if is_rate_limit and attempt < max_attempts - 1:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Rate limit hit on turn %d (attempt %d/%d): %s. Retrying in %.2fs",
                        turn_id,
                        attempt + 1,
                        max_attempts,
                        err_str,
                        backoff,
                    )
                    self.sink.end_turn()
                    await asyncio.sleep(backoff)
                    continue

                err_msg = f"[Agent Warning: {err_str}]"
                self.sink.stream_token(err_msg)
                response_parts.append(f"\n{err_msg}")
                self.sink.end_turn()
                break

        full_response = "".join(response_parts)
        inspected = (
            self.agent_core.pop_inspected_files()
            if hasattr(self.agent_core, "pop_inspected_files")
            else []
        )
        # Extract incident if detected
        event = self.extractor.extract(turn_id, batch, full_response, inspected_files=inspected)
        if event:
            self.recorder.record(event)
