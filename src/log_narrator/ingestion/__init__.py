# log_narrator/ingestion/__init__.py
from log_narrator.ingestion.base import BaseLogReader
from log_narrator.ingestion.file_tailer import FileTailer
from log_narrator.ingestion.stdin_reader import StdinReader

__all__ = ["BaseLogReader", "FileTailer", "StdinReader"]
