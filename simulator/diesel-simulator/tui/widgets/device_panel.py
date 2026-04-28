from textual.app import ComposeResult
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Vertical, Horizontal

class DevicePanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="device-stats"):
            yield Label("[bold cyan]DIESEL STATUS[/]", id="title")

            with Horizontal(classes="stat-row"):
                yield Label("STATE: ", classes="stat-label")
                yield Label("OFF", id="state-val", classes="stat-value")
                yield Label(" | COMMS: ", classes="stat-label")
                yield Label("OK", id="comms-val", classes="alarm-normal")

            with Horizontal(id="alarm-row", classes="stat-row"):
                yield Label("ALARM: ", classes="stat-label")
                yield Label("NORMAL", id="alarm-val", classes="alarm-normal")

            # Engine section
            with Vertical(classes="stat-group"):
                with Horizontal(classes="stat-row"):
                    yield Label("POWER (P): ", classes="stat-label")
                    yield Label("0.0", id="power-val", classes="stat-value")
                    yield Label(" kW", classes="unit")
                    yield Label("   RPM: ", classes="stat-label")
                    yield Label("0", id="rpm-val", classes="stat-value")
                with Horizontal(classes="stat-row"):
                    yield Label("COOLANT:   ", classes="stat-label")
                    yield Label("0.0", id="coolant-val", classes="stat-value")
                    yield Label(" °C", classes="unit")
                    yield Label("   OIL: ", classes="stat-label")
                    yield Label("0.0", id="oil-val", classes="stat-value")
                    yield Label(" bar", classes="unit")

            # Fuel section
            with Vertical(classes="stat-group", id="fuel-group"):
                with Horizontal(classes="stat-row"):
                    yield Label("FUEL LEVEL: ", classes="stat-label")
                    yield Label("0.0 %", id="fuel-text", classes="stat-value")
                    yield Label("   RATE: ", classes="stat-label")
                    yield Label("0.0", id="fuel-rate-val", classes="stat-value")
                    yield Label(" L/h", classes="unit")
                with Horizontal(classes="stat-row"):
                    yield Label("REMAINING:  ", classes="stat-label")
                    yield Label("0.0", id="fuel-rem-val", classes="stat-value")
                    yield Label(" L", classes="unit")
                yield ProgressBar(total=100.0, show_eta=False, id="fuel-bar")

    def update_data(self, state: str, data: dict):
        self.query_one("#state-val").update(state)

        inst = data.get("instantaneous", {})
        self.query_one("#power-val").update(f"{inst.get('P', 0.0):.1f}")

        engine = data.get("engine", {})
        self.query_one("#rpm-val").update(f"{int(engine.get('rpm', 0))}")

        # Coolant temp with threshold coloring
        coolant = engine.get("coolant_temp", 0.0)
        coolant_label = self.query_one("#coolant-val")
        coolant_label.update(f"{coolant:.1f}")
        if coolant > 95.0:
            coolant_label.styles.color = "red"
        elif coolant > 85.0:
            coolant_label.styles.color = "yellow"
        else:
            coolant_label.styles.color = "#c0caf5"

        # Oil pressure with threshold coloring
        oil = engine.get("oil_pressure", 0.0)
        oil_label = self.query_one("#oil-val")
        oil_label.update(f"{oil:.1f}")
        if oil < 1.5:
            oil_label.styles.color = "red"
        else:
            oil_label.styles.color = "#c0caf5"

        fuel = data.get("fuel", {})
        fuel_pct = fuel.get("level_percent", 0.0)
        self.query_one("#fuel-text").update(f"{fuel_pct:.1f} %")
        self.query_one("#fuel-bar").update(progress=fuel_pct)
        self.query_one("#fuel-rate-val").update(f"{fuel.get('consumption_rate_lph', 0.0):.1f}")
        self.query_one("#fuel-rem-val").update(f"{fuel.get('remaining_liters', 0.0):.1f}")

        # comms_health
        comms = data.get("status", {}).get("comms_health", "ok")
        comms_label = self.query_one("#comms-val")
        if comms == "ok":
            comms_label.update("OK")
            comms_label.set_classes("alarm-normal")
        else:
            comms_label.update(comms.upper())
            comms_label.set_classes("alarm-error")

        # Alarm
        alarm_label = self.query_one("#alarm-val")
        if state == "FAULT":
            alarm_label.update("FAULT DETECTED")
            alarm_label.set_classes("alarm-error")
        elif fuel_pct < 10.0 and state == "RUNNING":
            alarm_label.update("LOW FUEL CRITICAL")
            alarm_label.set_classes("alarm-error")
        elif fuel_pct < 20.0 and state == "RUNNING":
            alarm_label.update("LOW FUEL WARNING")
            alarm_label.set_classes("alarm-warning")
        else:
            alarm_label.update("NORMAL")
            alarm_label.set_classes("alarm-normal")

        # State color
        state_label = self.query_one("#state-val")
        if state == "RUNNING":
            state_label.styles.color = "green"
        elif state in ["STARTING", "STOPPING"]:
            state_label.styles.color = "yellow"
        elif state == "FAULT":
            state_label.styles.color = "red"
        else:
            state_label.styles.color = "white"
