from textual.app import ComposeResult
from textual.widgets import Button, Input, Static, Label, Select
from textual.containers import Horizontal, Vertical

class ControlPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="control-area"):
            yield Label("[bold]CONTROLS[/]", id="control-title")
            
            yield Label("Target Device", classes="sub-title")
            yield Select([], id="select-device", prompt="Select Device...")
            
            yield Button("RESET FAULT (R)", id="btn-reset", variant="warning")
            
            yield Label("Curtailment (Limit kW)", classes="sub-title")
            with Horizontal(id="curtail-input-group"):
                yield Input(placeholder="Limit kW...", id="input-limit")
                yield Button("SET (L)", id="btn-set-limit", variant="primary")
                
    def add_device(self, device_id: str):
        select = self.query_one("#select-device", Select)
        options = [(label, val) for label, val in select._options]
        # Check if already exists
        if not any(val == device_id for _, val in options):
            options.append((device_id, device_id))
            select.set_options(options)
            if select.value == Select.BLANK:
                select.value = device_id
