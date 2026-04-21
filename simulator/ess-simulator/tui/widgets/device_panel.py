from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable, Static


class DevicePanel(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rows: dict[str, tuple[str, ...]] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="fleet-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Device", "State", "Mode", "SOC", "P(kW)", "Temp(C)", "Energy(kWh)", "Link")

    def seed_devices(self, device_ids: list[str]) -> None:
        for device_id in device_ids:
            self.rows[device_id] = (device_id, "WAITING", "standby", "-", "-", "-", "-", "offline")
        self._render_rows()

    def update_device(self, device_id: str, payload: dict) -> None:
        data = payload.get("data", {})
        instantaneous = data.get("instantaneous", {})
        energy = data.get("energy", {})
        status = data.get("status", {})

        self.rows[device_id] = (
            device_id,
            str(payload.get("state", status.get("state", "LIVE"))),
            str(status.get("operating_mode", "standby")),
            f"{status.get('SOC', 0.0):.1f}",
            f"{instantaneous.get('P', 0.0):.1f}",
            f"{payload.get('temperature_c', 0.0):.1f}",
            f"{energy.get('kWh', 0.0):.2f}",
            str(status.get("comms_health", "ok")),
        )
        self._render_rows()

    def _render_rows(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=False)
        for device_id in sorted(self.rows):
            table.add_row(*self.rows[device_id], key=device_id)
