from log_narrator.config import DEFAULT_IGNORED_PATTERNS
from log_narrator.engine.preprocessor import LogPreprocessor


def test_heartbeat_filtering():
    filter_engine = LogPreprocessor(ignored_patterns=DEFAULT_IGNORED_PATTERNS)
    assert filter_engine.is_ignored("127.0.0.1 - - [19/Sep/2026] GET /health 200")
    assert filter_engine.is_ignored("service ping pong ok")
    assert not filter_engine.is_ignored("ERROR: Database connection timed out")
    assert not filter_engine.is_ignored("POST /api/v1/checkout 500")

def test_multiline_trace_detection():
    filter_engine = LogPreprocessor(ignored_patterns=[])
    assert filter_engine.is_multiline_start("Traceback (most recent call last):")
    assert filter_engine.is_multiline_start("panic: runtime error: invalid memory address")
    assert filter_engine.is_multiline_continuation('  File "main.py", line 42, in <module>')
    assert filter_engine.is_multiline_continuation("    at Object.<anonymous> (/app/index.js:12:3)")
    assert not filter_engine.is_multiline_start("2026-09-19 INFO Application started")
