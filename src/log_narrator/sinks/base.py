from abc import ABC, abstractmethod


class BaseOutputSink(ABC):
    """Abstract interface for log narrator output renderers."""

    @abstractmethod
    def emit_raw_log(self, line: str) -> None:
        """Display an incoming raw log line."""

    @abstractmethod
    def start_turn(self, turn_id: int) -> None:
        """Called when a new AI narrative stream starts."""

    @abstractmethod
    def stream_token(self, token: str) -> None:
        """Stream an AI narrative token."""

    def stream_thought(self, thought: str) -> None:  # noqa: B027
        """Stream an AI internal reasoning/thought token."""

    @abstractmethod
    def end_turn(self) -> None:
        """Called when current narrative stream finishes."""

    @abstractmethod
    def close(self) -> None:
        """Cleanup any active UI resources."""
