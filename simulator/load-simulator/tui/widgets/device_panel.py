from textual.app import ComposeResult
from textual.widgets import DataTable, Static


class DeviceTable(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.device_rows: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="load-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(
            "Device ID", "State", "Shed (%)", "P (kW)", "V (V)", "PF", "kWh", "Wire"
        )

    def update_device(self, device_id: str, data: dict) -> None:
        table = self.query_one(DataTable)
        inst = data.get("instantaneous", {})
        energy = data.get("energy", {})
        status = data.get("status", {})

        operating_state = status.get("operating_state", "IDLE")
        shed_ratio = status.get("shed_ratio", 0.0)
        comms_health = status.get("comms_health", "ok")

        if operating_state == "RUNNING":
            state_str = "[green]RUNNING[/]"
        elif operating_state == "SHED":
            state_str = "[yellow]SHED[/]"
        else:
            state_str = f"[white]{operating_state}[/]"

        shed_str = f"{shed_ratio * 100:.0f}"
        wire_str = "[green]OK[/]" if comms_health == "ok" else "[red]WIRE_FAULT[/]"

        row_data = (
            device_id,
            state_str,
            shed_str,
            f"{inst.get('P', 0.0):.2f}",
            f"{inst.get('V', 0.0):.1f}",
            f"{inst.get('PF', 0.0):.2f}",
            f"{energy.get('kWh', 0.0):.1f}",
            wire_str,
        )

        if device_id not in self.device_rows:
            row_key = table.add_row(*row_data, key=device_id)
            self.device_rows[device_id] = row_key
        else:
            col_keys = list(table.columns.keys())
            for col_idx, col_val in enumerate(row_data):
                table.update_cell(device_id, col_keys[col_idx], col_val)
