from datetime import datetime, timezone
from pathlib import Path

from log_narrator.engine.models import IncidentEvent


class IncidentRecorder:
    """Records diagnosed incidents and exports structured Markdown postmortems."""

    def __init__(self, export_path: Path | None = None) -> None:
        self.export_path = export_path
        self._incidents: list[IncidentEvent] = []

    def record(self, incident: IncidentEvent) -> None:
        self._incidents.append(incident)

    @property
    def incident_count(self) -> int:
        return len(self._incidents)

    @property
    def incidents(self) -> list[IncidentEvent]:
        return list(self._incidents)

    def generate_markdown(self) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "# LogNarrator Incident Postmortem",
            f"**Generated**: {now_str}  ",
            f"**Total Incidents Detected**: {self.incident_count}\n",
            "---",
        ]

        if not self._incidents:
            lines.append("\n*No critical incidents or unhandled exceptions recorded during this session.*")
            return "\n".join(lines)

        for i, inc in enumerate(self._incidents, start=1):
            ts_str = inc.timestamp.strftime("%H:%M:%S UTC")
            lines.extend([
                f"\n## Incident #{i}: {inc.headline} (`{inc.incident_id}`)",
                f"- **Detected At**: {ts_str}",
            ])
            if inc.inspected_files:
                files_str = ", ".join(f"`{f}`" for f in inc.inspected_files)
                lines.append(f"- **Source Files Inspected**: {files_str}")

            lines.extend([
                "\n### Raw Log Excerpt",
                "```text",
                inc.raw_log_snippet.strip(),
                "```",
                "\n### Root Cause Analysis",
                inc.root_cause.strip(),
                "\n### Recommended Remediation",
                inc.recommended_fix.strip(),
                "\n---",
            ])

        return "\n".join(lines)

    def export_markdown(self, path: Path | None = None) -> Path | None:
        target = path or self.export_path
        if not target:
            return None
        # Prevent exit crashes on read-only disk or storage errors
        try:
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = self.generate_markdown()
            target.write_text(content, encoding="utf-8")
            return target
        except OSError as e:
            import sys
            sys.stderr.write(f"\n[LogNarrator Warning] Failed to export postmortem to {target}: {e}\n")
            return None
