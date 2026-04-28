from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Vertical

class TopologyPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="topology-container"):
            yield Label("[bold cyan]TOPOLOGY[/]", id="topology-title")
            yield Label("No topology data", id="topology-content")

    def refresh_topology(self, lines: dict, switches: dict, device_ids: set):
        lines_for_device = {k: v for k, v in lines.items()
                            if device_ids & set(v.get("affected_devices", []))}
        switches_for_device = {k: v for k, v in switches.items()
                               if device_ids & set(v.get("affected_devices", []))}

        parts = []
        for line_id, line_data in lines_for_device.items():
            status = line_data.get("status", "UNKNOWN")
            if status == "FAULT":
                parts.append(f"Line  : {line_id:<26} [bold red]{status}  ✗[/]")
            elif status == "BLOCKED":
                parts.append(f"Line  : {line_id:<26} [yellow]{status} ⚠[/]")
            else:
                parts.append(f"Line  : {line_id:<26} [green]{status} ✓[/]")

        for sw_id, sw_data in switches_for_device.items():
            status = sw_data.get("status", "UNKNOWN")
            if status == "FAULT":
                parts.append(f"Switch: {sw_id:<26} [bold red]{status}  ✗[/]")
            elif status in ("OPEN", "TRANSITIONING"):
                parts.append(f"Switch: {sw_id:<26} [yellow]{status} ⚠[/]")
            else:
                parts.append(f"Switch: {sw_id:<26} [green]{status} ✓[/]")

        content = self.query_one("#topology-content")
        if parts:
            content.update("\n".join(parts))
        else:
            content.update("No topology entries for ESS devices")
