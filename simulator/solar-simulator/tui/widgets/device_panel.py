from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Vertical, Horizontal

class DevicePanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="device-stats"):
            yield Label("[bold yellow]SOLAR STATUS (Left Panel)[/]", id="title")
            
            # 논리적 상태 및 동작 모드
            with Horizontal(classes="stat-row"):
                yield Label("STATE: ", classes="stat-label")
                yield Label("STANDBY", id="state-val", classes="stat-value")
                yield Label(" | MODE: ", classes="stat-label")
                yield Label("AUTO", id="mode-val", classes="stat-value")
            
            # 장애/비상 알람 상태
            with Horizontal(id="alarm-row", classes="stat-row"):
                yield Label("ALARM: ", classes="stat-label")
                yield Label("NORMAL", id="alarm-val", classes="alarm-normal")

            # 실시간 수치 데이터
            with Vertical(classes="stat-group"):
                with Horizontal(classes="stat-row"):
                    yield Label("POWER (P): ", classes="stat-label")
                    yield Label("0.0", id="power-val", classes="stat-value")
                    yield Label(" kW", classes="unit")
                with Horizontal(classes="stat-row"):
                    yield Label("VOLTAGE (V): ", classes="stat-label")
                    yield Label("0.0", id="voltage-val", classes="stat-value")
                    yield Label(" V", classes="unit")
                with Horizontal(classes="stat-row"):
                    yield Label("CURRENT (I): ", classes="stat-label")
                    yield Label("0.0", id="current-val", classes="stat-value")
                    yield Label(" A", classes="unit")
                with Horizontal(classes="stat-row"):
                    yield Label("FREQUENCY (f): ", classes="stat-label")
                    yield Label("60.0", id="freq-val", classes="stat-value")
                    yield Label(" Hz", classes="unit")

    def update_data(self, state: str, data: dict):
        self.query_one("#state-val").update(state)
        
        inst = data.get("instantaneous", {})
        self.query_one("#power-val").update(f"{inst.get('P', 0.0):.2f}")
        self.query_one("#voltage-val").update(f"{inst.get('V', 0.0):.1f}")
        self.query_one("#current-val").update(f"{inst.get('I', 0.0):.2f}")
        self.query_one("#freq-val").update(f"{inst.get('f', 60.0):.1f}")
        
        # 알람 상태
        alarm_label = self.query_one("#alarm-val")
        if state == "FAULT":
            alarm_label.update("FAULT DETECTED")
            alarm_label.set_classes("alarm-error")
        else:
            alarm_label.update("NORMAL")
            alarm_label.set_classes("alarm-normal")
        
        # 상태 색상 변경
        state_label = self.query_one("#state-val")
        if state == "GENERATING":
            state_label.styles.color = "green"
        elif state == "FAULT":
            state_label.styles.color = "red"
        else:
            state_label.styles.color = "white"
