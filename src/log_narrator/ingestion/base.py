from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLogReader(ABC):
    """Abstract base class for all log ingestion sources."""

    @abstractmethod
    def stream(self) -> AsyncIterator[str]:
        """Yield log lines as strings asynchronously."""

    @abstractmethod
    async def stop(self) -> None:
        """Signal the reader to terminate gracefully."""
