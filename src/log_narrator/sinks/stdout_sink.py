import sys

from log_narrator.sinks.base import BaseOutputSink


class StdoutSink(BaseOutputSink):
    """Simple non-interactive stdout stream sink."""

    def __init__(self, show_raw_logs: bool = True) -> None:
        self.show_raw_logs = show_raw_logs
        self._broken_pipe = False

    def emit_raw_log(self, line: str) -> None:
        if not self.show_raw_logs or self._broken_pipe:
            return
        try:
            print(f"\033[90m[RAW]\033[0m {line}")
        except BrokenPipeError:
            self._broken_pipe = True

    def start_turn(self, turn_id: int) -> None:
        if self._broken_pipe:
            return
        try:
            print(f"\n\033[1;36m─── LogNarrator [Turn {turn_id}] ───\033[0m")
        except BrokenPipeError:
            self._broken_pipe = True

    def stream_token(self, token: str) -> None:
        if self._broken_pipe:
            return
        try:
            sys.stdout.write(token)
            sys.stdout.flush()
        except BrokenPipeError:
            self._broken_pipe = True

    def stream_thought(self, thought: str) -> None:
        if self._broken_pipe:
            return
        try:
            sys.stdout.write(f"\033[2;3m{thought}\033[0m")
            sys.stdout.flush()
        except BrokenPipeError:
            self._broken_pipe = True

    def end_turn(self) -> None:
        if self._broken_pipe:
            return
        try:
            print("\n")
        except BrokenPipeError:
            self._broken_pipe = True

    def close(self) -> None:
        pass

