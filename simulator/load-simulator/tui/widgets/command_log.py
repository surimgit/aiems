from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import RichLog, Static


class CommandLog(Static):
    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, id="log-view")

    def log_message(self, message: str, level: str = "info") -> None:
        log_view = self.query_one("#log-view")
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "error" or "rejected" in message.lower():
            color = "red"
        elif level == "success" or "accepted" in message.lower():
            color = "green"
        elif level == "warning":
            color = "yellow"
        else:
            color = "white"
        log_view.write(f"[{timestamp}] [{color}]{message}[/]")
