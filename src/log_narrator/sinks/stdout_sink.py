import sys

from log_narrator.sinks.base import BaseOutputSink


class StdoutSink(BaseOutputSink):
    """Simple non-interactive stdout stream sink."""

    def __init__(self, show_raw_logs: bool = True) -> None:
        self.show_raw_logs = show_raw_logs

    def emit_raw_log(self, line: str) -> None:
        if self.show_raw_logs:
            print(f"\033[90m[RAW]\033[0m {line}")

    def start_turn(self, turn_id: int) -> None:
        print(f"\n\033[1;36m─── LogNarrator [Turn {turn_id}] ───\033[0m")

    def stream_token(self, token: str) -> None:
        sys.stdout.write(token)
        sys.stdout.flush()

    def stream_thought(self, thought: str) -> None:
        sys.stdout.write(f"\033[2;3m{thought}\033[0m")
        sys.stdout.flush()

    def end_turn(self) -> None:
        print("\n")

    def close(self) -> None:
        pass
