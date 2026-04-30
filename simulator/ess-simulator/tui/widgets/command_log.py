from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import RichLog, Static


class CommandLog(Static):
    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, id="log-view")

    def log_message(self, message: str, level: str = "info") -> None:
        log_view = self.query_one(RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "white"
        if level == "error":
            color = "red"
        elif level == "success":
            color = "green"
        elif level == "warning":
            color = "yellow"
        log_view.write(f"[{timestamp}] [{color}]{message}[/]")
