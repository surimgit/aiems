from textual.app import ComposeResult
from textual.widgets import Button, Input, Static, Label
from textual.containers import Horizontal, Vertical

class ControlPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="control-area"):
            yield Label("[bold]CONTROLS[/]", id="control-title")
            
            yield Button("RESET FAULT (R)", id="btn-reset", variant="warning")
            
            yield Label("Curtailment (Limit kW)", classes="sub-title")
            with Horizontal(id="curtail-input-group"):
                yield Input(placeholder="Limit kW...", id="input-limit")
                yield Button("SET (L)", id="btn-set-limit", variant="primary")
