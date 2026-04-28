from textual.app import ComposeResult
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical


class ControlPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="ctrl-container"):
            yield Label("[bold yellow]CONTROL[/]", id="ctrl-title")
            with Horizontal(id="select-row"):
                yield Label("Target: ", classes="ctrl-label")
                yield Select([], id="select-device", allow_blank=True)
            with Horizontal(id="action-buttons"):
                yield Button("SHED", id="btn-shed", variant="warning")
                yield Button("RESTORE", id="btn-restore", variant="success")
            with Horizontal(id="ratio-input-group"):
                yield Input(placeholder="Shed Ratio (0-100%)", id="input-shed-ratio")
                yield Button("SET", id="btn-set-ratio", variant="primary")

    def add_device(self, device_id: str) -> None:
        select = self.query_one("#select-device", Select)
        current = [(str(v), v) for v in select._options] if hasattr(select, "_options") else []
        try:
            opts = list(select._options)
            ids = [v for _, v in opts]
            if device_id not in ids:
                select.set_options([(v, v) for _, v in opts] + [(device_id, device_id)])
        except Exception:
            pass

    def set_device_list(self, device_ids: list[str]) -> None:
        select = self.query_one("#select-device", Select)
        select.set_options([(d, d) for d in device_ids])
