import logging
import re
from collections import deque

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from log_narrator.sinks.base import BaseOutputSink

logger = logging.getLogger(__name__)


class _RawLogsRenderable:
    def __init__(self, sink: "RichTUIOutputSink") -> None:
        self._sink = sink

    def __rich__(self) -> Panel:
        return self._sink._render_raw_panel()


class _NarratorRenderable:
    def __init__(self, sink: "RichTUIOutputSink") -> None:
        self._sink = sink

    def __rich__(self) -> Panel:
        return self._sink._render_narrator_panel()


class RichTUIOutputSink(BaseOutputSink):
    """Split-screen live TUI displaying raw log stream alongside streaming AI narrative."""

    def __init__(
        self,
        max_raw_lines: int = 30,
        auto_start: bool = True,
        console: Console | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self.console = console or Console(width=width, height=height)
        self.max_raw_lines = max_raw_lines
        self.raw_lines: deque[str] = deque(maxlen=max_raw_lines)
        self.current_narrative = ""
        self.current_thoughts = ""
        self._in_stream = False
        self.layout = Layout()
        self._setup_layout()
        self.live = Live(self.layout, console=self.console, refresh_per_second=10, auto_refresh=True, transient=False)
        if auto_start:
            self.start()

    def start(self) -> None:
        if not self.live.is_started:
            self.live.start()

    def _setup_layout(self) -> None:
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        self.layout["body"].split_row(
            Layout(name="raw_logs", ratio=1),
            Layout(name="narrator", ratio=1),
        )
        self._render_header()
        self._render_footer()
        self.layout["raw_logs"].update(_RawLogsRenderable(self))
        self.layout["narrator"].update(_NarratorRenderable(self))

    def _render_header(self) -> None:
        grid = Text.assemble(
            (" ⚡ LogNarrator ", "bold #8aadf4"),
            ("│ ", "dim #939ab7"),
            ("Autonomous Log Translator & Diagnostic Copilot", "bold #cad3f5"),
            ("   [LIVE TRIAGE]", "bold #a6da95"),
        )
        self.layout["header"].update(Panel(grid, box=box.ROUNDED, style="dim #8aadf4", border_style="#8aadf4"))

    def _render_footer(self) -> None:
        text = Text.assemble(
            (" [Ctrl+C] ", "bold #cad3f5 on #363a4f"),
            (" Terminate session & generate incident postmortem dossier", "dim #939ab7"),
            ("  •  Engine: active", "bold #a6da95"),
        )
        self.layout["footer"].update(Panel(text, box=box.ROUNDED, style="dim", border_style="#494d64"))

    def _render_body(self) -> None:
        """Triggers a display refresh without overwriting dynamic renderables."""
        if self.live.is_started:
            self.live.refresh()

    def _render_raw_panel(self) -> Panel:
        if self.raw_lines:
            log_text = Text()
            for line in self.raw_lines:
                formatted_line = self._format_log_line(line)
                log_text.append_text(formatted_line)
                log_text.append("\n")
        else:
            log_text = Text("Waiting for incoming log stream...", style="dim italic")

        return Panel(
            log_text,
            title="[bold #8aadf4] 📥 Incoming Raw Logs [/bold #8aadf4]",
            title_align="left",
            box=box.ROUNDED,
            border_style="#8aadf4",
        )

    def _render_narrator_panel(self) -> Panel:
        if self.current_narrative:
            if self._in_stream:
                if self.current_thoughts:
                    narrative_renderable = Text(f"> [Thinking...]\n\n{self.current_narrative}")
                else:
                    narrative_renderable = Text(self.current_narrative)
            else:
                narrative_content = self.current_narrative
                if self.current_thoughts:
                    narrative_content = f"> *Thinking: {self.current_thoughts}*\n\n{self.current_narrative}"
                narrative_renderable = Markdown(narrative_content)
        elif self.current_thoughts:
            narrative_renderable = Text(f"Thinking: {self.current_thoughts}", style="dim italic")
        else:
            narrative_renderable = Text("Listening for incident clusters...", style="dim italic")

        return Panel(
            narrative_renderable,
            title="[bold #a6da95] 🔍 AI Diagnostic Narrative [/bold #a6da95]",
            title_align="left",
            box=box.ROUNDED,
            border_style="#a6da95",
        )

    def _format_log_line(self, line: str) -> Text:
        t = Text()
        if " [FATAL] " in line or " [CRITICAL] " in line:
            parts = re.split(r"( \[(?:FATAL|CRITICAL)\] )", line, maxsplit=1)
            t.append(parts[0], style="dim #91d7e3")
            t.append(parts[1], style="bold #181926 on #ed8796")
            t.append(parts[2], style="bold #ed8796")
        elif " [ERROR] " in line:
            parts = line.split(" [ERROR] ", 1)
            t.append(parts[0], style="dim #91d7e3")
            t.append(" [ERROR] ", style="bold #ed8796")
            t.append(parts[1], style="#ee99a0")
        elif " [WARN] " in line:
            parts = line.split(" [WARN] ", 1)
            t.append(parts[0], style="dim #91d7e3")
            t.append(" [WARN] ", style="bold #eed49f")
            t.append(parts[1], style="#eed49f")
        elif " [INFO] " in line:
            parts = line.split(" [INFO] ", 1)
            t.append(parts[0], style="dim #91d7e3")
            t.append(" [INFO] ", style="bold #a6da95")
            t.append(parts[1], style="#cad3f5")
        elif line.startswith("Traceback") or line.strip().startswith("File "):
            t.append(line, style="#ee99a0")
        elif "Error:" in line or "Exception:" in line:
            t.append(line, style="bold #ed8796")
        else:
            t.append(line, style="#a5adcb")
        return t

    def emit_raw_log(self, line: str) -> None:
        self.raw_lines.append(line)

    def start_turn(self, turn_id: int) -> None:
        self._in_stream = True
        self.current_narrative = ""
        self.current_thoughts = ""
        if self.live.is_started:
            self.live.refresh()

    def stream_thought(self, thought: str) -> None:
        self.current_thoughts += thought

    def stream_token(self, token: str) -> None:
        self.current_narrative += token

    def end_turn(self) -> None:
        self._in_stream = False
        if self.live.is_started:
            self.live.refresh()

    def close(self) -> None:
        try:
            self.live.stop()
        except Exception as e:
            logger.warning("Error stopping Rich live console: %s", e)
