from textual.app import ComposeResult
from textual.widgets import Button, Input, Static, Label
from textual.containers import Horizontal, Vertical

class ControlPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="control-area"):
            yield Label("[bold]CONTROLS[/]", id="control-title")
            yield Button("START (S)", id="btn-start", variant="success")
            yield Button("STOP (X)", id="btn-stop", variant="error")
            
            yield Label("Load Control", classes="sub-title")
            with Horizontal(id="load-input-group"):
                yield Input(placeholder="0.0", id="input-load")
                yield Button("SET (L)", id="btn-set-load", variant="primary")
