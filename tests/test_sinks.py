import pytest

from log_narrator.coordinator import PipelineCoordinator
from log_narrator.sinks.stdout_sink import StdoutSink


def test_stdout_sink_formatting(capsys):
    sink = StdoutSink(show_raw_logs=True)
    sink.emit_raw_log("2026-09-19 INFO Test log")
    sink.start_turn(turn_id=1)
    sink.stream_token("System ")
    sink.stream_token("healthy.")
    sink.end_turn()

    captured = capsys.readouterr()
    assert "Test log" in captured.out
    assert "System healthy." in captured.out

def test_unknown_sink_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported sink type 'invalid_sink'"):
        PipelineCoordinator._create_sink("invalid_sink")


def test_rich_tui_sink_raw_log_emission():
    from rich.console import Console

    from log_narrator.sinks.rich_tui import RichTUIOutputSink

    sink = RichTUIOutputSink(max_raw_lines=5, auto_start=False)
    sink.emit_raw_log("2026-09-19 ERROR database connection timeout")

    console = Console(width=100)
    with console.capture() as cap:
        console.print(sink.layout)
    out = cap.get()

    assert "database connection" in out
    assert "timeout" in out


def test_rich_tui_sink_streaming_lifecycle():
    from rich.console import Console

    from log_narrator.sinks.rich_tui import RichTUIOutputSink

    sink = RichTUIOutputSink(auto_start=False)
    sink.start_turn(turn_id=1)
    sink.stream_thought("Analyzing trace...")
    sink.stream_token("Memory leak detected")

    console = Console(width=100)
    with console.capture() as cap:
        console.print(sink.layout)
    streaming_out = cap.get()
    assert "Memory leak detected" in streaming_out

    sink.end_turn()
    with console.capture() as cap:
        console.print(sink.layout)
    completed_out = cap.get()
    assert "Memory leak detected" in completed_out


def test_rich_tui_sink_close_graceful():
    from log_narrator.sinks.rich_tui import RichTUIOutputSink

    sink = RichTUIOutputSink(auto_start=False)
    # Closing an unstarted or started sink should not raise
    sink.close()


def test_stdout_sink_handles_broken_pipe():
    from unittest.mock import patch

    sink = StdoutSink()
    with patch("sys.stdout.write", side_effect=BrokenPipeError):
        # Should not raise exception
        sink.stream_token("test token")
        sink.stream_thought("test thought")
        sink.emit_raw_log("test raw log")
        sink.start_turn(1)
        sink.end_turn()


