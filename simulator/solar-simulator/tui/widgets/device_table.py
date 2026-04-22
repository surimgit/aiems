from textual.app import ComposeResult
from textual.widgets import DataTable, Static, Label
from textual.containers import Vertical

class DeviceTable(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.device_rows = {} # device_id -> row_key

    def compose(self) -> ComposeResult:
        with Vertical(id="device-table-container"):
            yield Label("[bold yellow]MULTI-DEVICE TELEMETRY (0.1s Update)[/]", id="table-title")
            yield DataTable(id="telemetry-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Device ID", "Comm State", "Op State", "Alarm", "Power (kW)", "Voltage (V)", "Current (A)")

    def update_data(self, device_id: str, payload_data: dict, comms_health: str, current_state: str):
        table = self.query_one(DataTable)
        
        inst = payload_data.get("instantaneous", {})
        p_val = inst.get("P", 0.0)
        v_val = inst.get("V", 0.0)
        i_val = inst.get("I", 0.0)
        
        # State Formatting
        state_str = f"[green]GENERATING[/]" if current_state == "GENERATING" else f"[white]{current_state}[/]"
        if current_state == "FAULT":
            state_str = f"[bold red]FAULT[/]"
            
        alarm_str = "[red]FAULT DETECTED[/]" if current_state == "FAULT" else "[green]NORMAL[/]"
        comm_str = f"[green]{comms_health.upper()}[/]" if comms_health == "ok" else f"[red]{comms_health.upper()}[/]"
        
        row_data = (
            device_id,
            comm_str,
            state_str,
            alarm_str,
            f"{p_val:.2f}",
            f"{v_val:.1f}",
            f"{i_val:.2f}"
        )

        if device_id not in self.device_rows:
            # Add new row
            row_key = table.add_row(*row_data)
            self.device_rows[device_id] = row_key
        else:
            # Update specific row to prevent flickering (0.1s safe)
            row_key = self.device_rows[device_id]
            for col_idx, col_val in enumerate(row_data):
                # Textual DataTable requires ColumnKey for updating cells
                # To safely update by index, we get the Ordered Keys from table.columns
                col_key = list(table.columns.keys())[col_idx]
                table.update_cell(row_key, col_key, col_val)

