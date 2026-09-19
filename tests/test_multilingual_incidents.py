from log_narrator.engine.incident_extractor import IncidentExtractor
from log_narrator.engine.models import LogBatch, LogLine


def test_multilingual_panic_semantic_extraction():
    extractor = IncidentExtractor()

    # Go panic
    go_batch = LogBatch(source="server.go", lines=[LogLine(content="panic: runtime error: invalid memory address")])
    event = extractor.extract(1, go_batch, "Routine logs")
    assert event is not None
    assert event.incident_id == "INC-001"
    assert event.headline == "Runtime Exception Detected"
    assert "panic: runtime error" in event.raw_log_snippet

    # Java exception with explicit AI headline
    java_batch = LogBatch(source="app.log", lines=[LogLine(content='Exception in thread "main" java.lang.NullPointerException')])
    ai_narrative = "[INCIDENT: Null Pointer in Payment Gateway]\nCaused by uninitialized auth context."
    event = extractor.extract(2, java_batch, ai_narrative)
    assert event is not None
    assert event.incident_id == "INC-002"
    assert event.headline == "Null Pointer in Payment Gateway"
    assert "Payment Gateway" in event.headline

    # Rust / C++ fatal error / SIGSEGV
    rust_batch = LogBatch(source="core", lines=[LogLine(content="fatal error: glibc detected invalid pointer\nSIGSEGV")])
    event = extractor.extract(3, rust_batch, "Routine logs")
    assert event is not None
    assert event.incident_id == "INC-003"
    assert event.headline == "Runtime Exception Detected"
    assert "SIGSEGV" in event.raw_log_snippet

    # Benign log must produce None
    benign_batch = LogBatch(source="app.log", lines=[LogLine(content="User 123 logged in successfully")])
    assert extractor.extract(4, benign_batch, "Routine user login.") is None
