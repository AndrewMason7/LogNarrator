import re

from log_narrator.engine.models import IncidentEvent, LogBatch

RUNTIME_PANIC_SIGNATURES = re.compile(
    r"(Traceback \(most recent call last\):|panic: |Exception in thread \"|fatal error: |SIGSEGV|UnhandledPromiseRejection)",
    re.MULTILINE,
)

ROOT_CAUSE_PATTERN = re.compile(
    r"(?:#{1,6}\s*|\*{1,2}\s*)?(?:Root\s+Cause|Cause)(?:\*{1,2})?:?\s*(.*?)(?=(?:#{1,6}\s*|\*{1,2}\s*)?(?:Recommended\s+(?:Fix|Action|Remediation)|Remediation|Fix|Action)(?:\*{1,2})?:?|\Z)",
    re.IGNORECASE | re.DOTALL,
)

REMEDIATION_PATTERN = re.compile(
    r"(?:#{1,6}\s*|\*{1,2}\s*)?(?:Recommended\s+(?:Fix|Action|Remediation)|Remediation|Fix|Action)(?:\*{1,2})?:?\s*(.*?)(?=\Z)",
    re.IGNORECASE | re.DOTALL,
)


class IncidentExtractor:
    """Extracts structured IncidentEvents from AI diagnostic narratives and raw log batches."""

    def __init__(self, incident_pattern: str = r"\[INCIDENT:\s*([^\]\n]+)\]?") -> None:
        self.incident_pattern = re.compile(incident_pattern)

    def extract(
        self,
        turn_id: int,
        batch: LogBatch,
        narrative: str,
        inspected_files: list[str] | None = None,
    ) -> IncidentEvent | None:
        """Detects if an incident occurred and constructs an IncidentEvent."""
        incident_match = self.incident_pattern.search(narrative)
        has_panic = bool(RUNTIME_PANIC_SIGNATURES.search(batch.raw_text))

        if not incident_match and not has_panic:
            return None

        headline = incident_match.group(1).strip() if incident_match else "Runtime Exception Detected"

        rc_match = ROOT_CAUSE_PATTERN.search(narrative)
        if rc_match and rc_match.group(1).strip():
            root_cause = rc_match.group(1).strip().strip("*#").strip()
        else:
            root_cause = narrative

        fix_match = REMEDIATION_PATTERN.search(narrative)
        if fix_match and fix_match.group(1).strip():
            recommended_fix = fix_match.group(1).strip().strip("*#").strip()
        else:
            recommended_fix = "Review diagnostic narrative and inspect relevant source files."

        return IncidentEvent(
            incident_id=f"INC-{turn_id:03d}",
            headline=headline,
            raw_log_snippet=batch.raw_text,
            root_cause=root_cause,
            recommended_fix=recommended_fix,
            inspected_files=inspected_files or [],
        )
