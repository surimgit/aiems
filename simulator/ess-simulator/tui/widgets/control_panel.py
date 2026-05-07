from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical


class ControlPanel(Static):
    def __init__(self, device_ids: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._device_ids = device_ids or []

    def compose(self) -> ComposeResult:
        with Vertical(id="control-container"):
            yield Label("[bold yellow]CONTROL[/]", id="ctrl-title")
            with Horizontal(id="device-select-row"):
                yield Label("Target: ", classes="ctrl-label")
                yield Select(
                    [(d, d) for d in self._device_ids],
                    id="select-device",
                    allow_blank=True,
                )
            with Horizontal(id="mode-buttons"):
                yield Button("CHARGE", id="btn-charge", variant="success")
                yield Button("DISCHARGE", id="btn-discharge", variant="warning")
                yield Button("STANDBY", id="btn-standby", variant="default")
            with Horizontal(id="power-input-group"):
                yield Input(placeholder="Power (kW)", id="input-power")
                yield Button("SET", id="btn-set-power", variant="primary")

    def seed_devices(self, device_ids: list[str]) -> None:
        select = self.query_one("#select-device", Select)
        select.set_options([(d, d) for d in device_ids])
