from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import DataTable, Label, Static
from textual.containers import Vertical


class CommandTracker(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="tracker-container"):
            yield Label("[bold magenta]COMMAND TRACKER[/]", id="tracker-title")
            yield DataTable(id="cmd-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Time", "Command ID", "Type", "Target", "Status")

    def add_command(self, cmd_id: str, cmd_type: str, target: str, status: str) -> None:
        table = self.query_one(DataTable)
        time_str = datetime.now().strftime("%H:%M:%S")
        table.add_row(time_str, cmd_id, cmd_type, target, status, key=cmd_id)
        table.scroll_end(animate=False)

    def update_status(self, cmd_id: str, status: str) -> None:
        table = self.query_one(DataTable)
        try:
            col_keys = list(table.columns.keys())
            status_col = col_keys[4]
            table.update_cell(cmd_id, status_col, status)
        except Exception:
            pass
