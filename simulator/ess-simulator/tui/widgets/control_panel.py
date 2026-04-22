from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, Static


class ControlPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("ESS Fleet Monitor")
        yield Label("1. 4개 저장소 상태를 동시에 표시")
        yield Label("2. MQTT telemetry/ack 수신 시 즉시 갱신")
        yield Label("3. 현재는 상태 확인용, 제어 UI는 후속 작업")
