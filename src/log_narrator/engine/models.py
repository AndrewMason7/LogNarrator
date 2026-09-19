from datetime import datetime, timezone

from pydantic import BaseModel, Field


class LogLine(BaseModel):
    content: str
    line_number: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_multiline_continuation: bool = False

class LogBatch(BaseModel):
    lines: list[LogLine]
    source: str = "stream"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_lines(self) -> int:
        return len(self.lines)

    @property
    def raw_text(self) -> str:
        return "\n".join(line.content for line in self.lines)

class IncidentEvent(BaseModel):
    incident_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    headline: str
    raw_log_snippet: str
    root_cause: str
    recommended_fix: str
    inspected_files: list[str] = Field(default_factory=list)

class IncidentDossier(BaseModel):
    headline: str = Field(description="Brief, executive headline describing the incident")
    severity: str = Field(default="INFO", description="Incident severity level: INFO, WARNING, ERROR, CRITICAL")
    root_cause: str = Field(description="Underlying root cause determined by log and code analysis")
    recommended_fix: str = Field(description="Actionable steps or code patch to resolve the issue")
    affected_components: list[str] = Field(default_factory=list, description="Components or services affected")
