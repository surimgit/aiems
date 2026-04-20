from textual.app import ComposeResult
from textual.widgets import Static, Label, Digits, ProgressBar
from textual.containers import Vertical, Horizontal

class DevicePanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="device-stats"):
            yield Label("[bold cyan]DIESEL STATUS (Left Panel)[/]", id="title")
            
            # 논리적 상태 및 동작 모드
            with Horizontal(classes="stat-row"):
                yield Label("STATE: ", classes="stat-label")
                yield Label("OFF", id="state-val", classes="stat-value")
                yield Label(" | MODE: ", classes="stat-label")
                yield Label("AUTO", id="mode-val", classes="stat-value")
            
            # 장애/비상 알람 상태 (시각적 강조)
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
                    yield Label("ENGINE RPM: ", classes="stat-label")
                    yield Label("0", id="rpm-val", classes="stat-value")

            # 프로그레스 바를 이용한 배터리/연료 잔량 표시
            with Vertical(classes="stat-group", id="fuel-group"):
                with Horizontal():
                    yield Label("FUEL LEVEL: ", classes="stat-label")
                    yield Label("0.0 %", id="fuel-text", classes="stat-value")
                yield ProgressBar(total=100.0, show_eta=False, id="fuel-bar")

    def update_data(self, state: str, data: dict):
        self.query_one("#state-val").update(state)
        
        inst = data.get("instantaneous", {})
        self.query_one("#power-val").update(f"{inst.get('P', 0.0):.1f}")
        self.query_one("#voltage-val").update(f"{inst.get('V', 0.0):.1f}")
        
        engine = data.get("engine", {})
        self.query_one("#rpm-val").update(f"{int(engine.get('rpm', 0))}")
        
        fuel = data.get("fuel", {})
        fuel_pct = fuel.get('level_percent', 0.0)
        self.query_one("#fuel-text").update(f"{fuel_pct:.1f} %")
        self.query_one("#fuel-bar").update(progress=fuel_pct)
        
        # 알람 상태 업데이트 (연료 10% 미만 시 경고)
        alarm_label = self.query_one("#alarm-val")
        if state == "FAULT":
            alarm_label.update("FAULT DETECTED")
            alarm_label.set_classes("alarm-error")
        elif fuel_pct < 10.0 and state == "RUNNING":
            alarm_label.update("LOW FUEL WARNING")
            alarm_label.set_classes("alarm-warning")
        else:
            alarm_label.update("NORMAL")
            alarm_label.set_classes("alarm-normal")
        
        # 상태 색상 변경
        state_label = self.query_one("#state-val")
        if state == "RUNNING":
            state_label.styles.color = "green"
        elif state in ["STARTING", "STOPPING"]:
            state_label.styles.color = "yellow"
        elif state == "FAULT":
            state_label.styles.color = "red"
        else:
            state_label.styles.color = "white"
