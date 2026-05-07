from textual.widgets import RichLog, Static
from textual.app import ComposeResult
from datetime import datetime

class CommandLog(Static):
    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, id="log-view")

    def log_message(self, message: str, level: str = "info"):
        log_view = self.query_one("#log-view")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        color = "white"
        if level == "error" or "rejected" in message.lower():
            color = "red"
        elif level == "success" or "accepted" in message.lower():
            color = "green"
        elif level == "warning":
            color = "yellow"
            
        log_view.write(f"[{timestamp}] [{color}]{message}[/]")
