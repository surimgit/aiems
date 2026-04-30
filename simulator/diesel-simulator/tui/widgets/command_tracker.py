from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from datetime import datetime

class CommandTracker(Static):
    def compose(self) -> ComposeResult:
        yield DataTable(id="cmd-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Time", "Command ID", "Type/Action", "Target", "Status")

    def add_command(self, cmd_id: str, action: str, target: str, status: str):
        table = self.query_one(DataTable)
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # 최근 명령이 위로 오도록 0번에 삽입 (또는 끝에 삽입 후 스크롤)
        table.add_row(time_str, cmd_id, action, target, status)
        table.scroll_end(animate=False)
