from textual.app import ComposeResult
from textual.widgets import Label, ProgressBar, Static
from textual.containers import Horizontal, Vertical

WARN_PCT = 80.0
CRIT_PCT = 95.0


class DemandPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="demand-container"):
            yield Label("[bold yellow]DEMAND[/]", id="demand-title")
            with Horizontal(classes="stat-row"):
                yield Label("Current P: ", classes="stat-label")
                yield Label("0.0 kW", id="demand-current")
            with Horizontal(classes="stat-row"):
                yield Label("Peak Max:  ", classes="stat-label")
                yield Label("0.0 kW", id="demand-peak")
            yield ProgressBar(total=100.0, show_eta=False, id="demand-bar")
            yield Label("", id="demand-warn")

    def update_demand(self, current_p: float, demand_max: float) -> None:
        self.query_one("#demand-current").update(f"{current_p:.1f} kW")
        self.query_one("#demand-peak").update(f"{demand_max:.1f} kW")

        if demand_max <= 0:
            pct = 0.0
        else:
            pct = min(current_p / demand_max * 100.0, 100.0)

        self.query_one("#demand-bar").update(progress=pct)

        warn_label = self.query_one("#demand-warn")
        if pct >= CRIT_PCT:
            warn_label.update(f"[bold red]⚠ CRITICAL: {pct:.1f}% of peak demand![/]")
        elif pct >= WARN_PCT:
            warn_label.update(f"[yellow]⚠ WARNING: {pct:.1f}% of peak demand[/]")
        else:
            warn_label.update(f"[green]{pct:.1f}% of peak demand[/]")
