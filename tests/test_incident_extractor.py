from log_narrator.engine.incident_extractor import IncidentExtractor
from log_narrator.engine.models import LogBatch, LogLine


def test_extract_incident_with_explicit_headline():
    extractor = IncidentExtractor()
    batch = LogBatch(lines=[LogLine(content="500 Internal Server Error", line_number=10)])
    narrative = "[INCIDENT: Database Pool Starvation]\nConnection pool exhausted."

    event = extractor.extract(turn_id=1, batch=batch, narrative=narrative)

    assert event is not None
    assert event.incident_id == "INC-001"
    assert event.headline == "Database Pool Starvation"
    assert event.raw_log_snippet == "500 Internal Server Error"
    assert event.root_cause == narrative

def test_extract_incident_from_traceback():
    extractor = IncidentExtractor()
    batch = LogBatch(lines=[LogLine(content="Traceback (most recent call last):\nKeyError: 'user_id'", line_number=20)])
    narrative = "A KeyError occurred in request handler."

    event = extractor.extract(turn_id=2, batch=batch, narrative=narrative)

    assert event is not None
    assert event.incident_id == "INC-002"
    assert event.headline == "Runtime Exception Detected"

def test_no_incident_for_healthy_logs():
    extractor = IncidentExtractor()
    batch = LogBatch(lines=[LogLine(content="GET /healthz 200", line_number=30)])
    narrative = "Routine health check succeeded."

    event = extractor.extract(turn_id=3, batch=batch, narrative=narrative)
    assert event is None


def test_extract_parses_root_cause_and_remediation():
    extractor = IncidentExtractor()
    batch = LogBatch(lines=[LogLine(content="panic: nil pointer dereference", line_number=1)])
    narrative = (
        "[INCIDENT: Database Null Pointer]\n\n"
        "Root Cause: The database pool returned a nil connection pointer after network timeout.\n\n"
        "Recommended Fix: Add nil check in db_pool.go and enable automatic reconnection."
    )
    event = extractor.extract(turn_id=1, batch=batch, narrative=narrative)
    assert event is not None
    assert "nil connection pointer" in event.root_cause
    assert "Add nil check" in event.recommended_fix
    assert event.recommended_fix != "See detailed AI narrative above."

