import re

MULTILINE_START_PATTERNS = [
    re.compile(r"^Traceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r"^panic:\s+", re.IGNORECASE),
    re.compile(r"^goroutine \d+ \[", re.IGNORECASE),
    re.compile(r"^[A-Za-z0-9_.]*(?:Error|Exception|Fault):\s+", re.IGNORECASE),
]

MULTILINE_CONTINUATION_PATTERNS = [
    re.compile(r"^\s+File \".*\", line \d+"),
    re.compile(r"^\s+at\s+.*\(.*:\d+:\d+\)"),
    re.compile(r"^\s+at\s+.*:\d+:\d+"),
    re.compile(r"^\s{2,}"),
    re.compile(r"^\t+"),
    re.compile(r"^\s*Caused by:\s+"),
]

class LogPreprocessor:
    """Filters noisy heartbeat lines and classifies multiline stack trace fragments."""

    def __init__(self, ignored_patterns: list[str]) -> None:
        # Compile ignored patterns into a single unified regex DFA
        if ignored_patterns:
            combined = "|".join(f"(?:{p})" for p in ignored_patterns)
            self.ignored_regex: re.Pattern | None = re.compile(combined, re.IGNORECASE)
        else:
            self.ignored_regex = None

    def is_ignored(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if self.ignored_regex:
            return bool(self.ignored_regex.search(line))
        return False

    def is_multiline_start(self, line: str) -> bool:
        stripped = line.strip()
        return any(pattern.search(stripped) for pattern in MULTILINE_START_PATTERNS)

    def is_multiline_continuation(self, line: str) -> bool:
        return any(pattern.search(line) for pattern in MULTILINE_CONTINUATION_PATTERNS)
