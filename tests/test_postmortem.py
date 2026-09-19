from datetime import datetime, timezone
from pathlib import Path

from log_narrator.engine.models import IncidentEvent
from log_narrator.recorder.postmortem import IncidentRecorder


def test_incident_recording_and_markdown_export(tmp_path: Path):
    export_file = tmp_path / "postmortem.md"
    recorder = IncidentRecorder(export_path=export_file)

    event = IncidentEvent(
        incident_id="INC-001",
        timestamp=datetime(2026, 9, 19, 5, 45, 0, tzinfo=timezone.utc),
        headline="Database Pool Exhaustion",
        raw_log_snippet="psycopg2.OperationalError: remaining connection slots are reserved",
        root_cause="Connection leak in worker loop without pool release.",
        recommended_fix="Wrap connection in context manager and bump max_connections.",
        inspected_files=["/app/db.py"],
    )
    recorder.record(event)
    assert recorder.incident_count == 1

    written_path = recorder.export_markdown()
    assert written_path == export_file
    content = export_file.read_text(encoding="utf-8")
    assert "# LogNarrator Incident Postmortem" in content
    assert "Database Pool Exhaustion" in content
    assert "/app/db.py" in content
    assert "INC-001" in content


def test_postmortem_session_observability():
    from unittest.mock import MagicMock
    recorder = IncidentRecorder()
    mock_usage = MagicMock()
    mock_usage.total_token_count = 18420
    mock_usage.prompt_token_count = 14200
    mock_usage.candidates_token_count = 4220
    mock_usage.thoughts_token_count = 800

    content = recorder.generate_markdown(usage=mock_usage, turn_count=3)
    assert "### Session Observability" in content
    assert "Total Diagnostic Turns**: 3" in content
    assert "18,420" in content
    assert "14,200" in content
    assert "4,220" in content
    assert "800" in content

