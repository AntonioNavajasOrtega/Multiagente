"""
simulation/visualizer.py

Visualización del estado de la simulación en terminal usando rich.
También imprime el grid ASCII con posiciones de vehículos.
"""
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from core.environment import (
    Grid, CELL_FREE, CELL_OBSTACLE, CELL_DEPOT,
    CELL_CLIENT, CELL_TRAFFIC
)
from core.entities import VehicleState

if TYPE_CHECKING:
    from agents.vehicle_agent import VehicleAgent
    from core.metrics import SimulationMetrics

# Colores rich por tipo de celda
CELL_STYLE = {
    CELL_FREE:     "white",
    CELL_OBSTACLE: "bold red",
    CELL_DEPOT:    "bold blue",
    CELL_CLIENT:   "bold green",
    CELL_TRAFFIC:  "bold yellow",
}

STATE_STYLE = {
    VehicleState.IDLE:            "dim",
    VehicleState.HEADING_DEPOT:   "blue",
    VehicleState.HEADING_CLIENT:  "green",
    VehicleState.DELIVERING:      "bold green",
}


class Visualizer:
    def __init__(self):
        self.console = Console() if HAS_RICH else None

    def print_grid(
        self,
        grid: Grid,
        vehicle_agents: List["VehicleAgent"],
        iteration: int,
    ) -> None:
        vehicle_pos: Dict = {}
        for va in vehicle_agents:
            pos = va.vehicle.pos
            vehicle_pos[pos] = va.vehicle.id

        if HAS_RICH and self.console:
            self._print_grid_rich(grid, vehicle_pos, iteration)
        else:
            self._print_grid_ascii(grid, vehicle_pos, iteration)

    def _print_grid_rich(self, grid: Grid, vehicle_pos: dict, iteration: int) -> None:
        self.console.print(f"\n[bold]Iteración {iteration}[/bold]")
        lines = []
        for r in range(grid.rows):
            row_text = Text()
            for c in range(grid.cols):
                pos = (r, c)
                if pos in vehicle_pos:
                    vid = vehicle_pos[pos]
                    row_text.append(f"[{vid[1]}]", style="bold magenta")
                else:
                    ct = grid.cells[r][c]
                    style = CELL_STYLE.get(ct, "white")
                    row_text.append(f"[{ct}]", style=style)
                row_text.append(" ")
            self.console.print(row_text)

    def _print_grid_ascii(self, grid: Grid, vehicle_pos: dict, iteration: int) -> None:
        print(f"\n=== Iteración {iteration} ===")
        print(grid.to_ascii(vehicle_pos))

    def print_vehicle_status(self, vehicle_agents: List["VehicleAgent"]) -> None:
        if HAS_RICH and self.console:
            table = Table(title="Estado de vehículos")
            table.add_column("ID")
            table.add_column("Pos")
            table.add_column("Estado")
            table.add_column("Carga")
            table.add_column("Destino dep.")
            table.add_column("Destino cli.")
            for va in vehicle_agents:
                v = va.vehicle
                style = STATE_STYLE.get(v.state, "")
                table.add_row(
                    v.id,
                    str(v.pos),
                    v.state.value,
                    str(v.current_load()),
                    v.target_depot or "-",
                    v.target_client or "-",
                    style=style,
                )
            self.console.print(table)
        else:
            for va in vehicle_agents:
                v = va.vehicle
                print(
                    f"  {v.id} | {v.pos} | {v.state.value:16s} | "
                    f"carga={v.current_load()} | dep={v.target_depot} | cli={v.target_client}"
                )

    def print_metrics_summary(self, metrics: "SimulationMetrics") -> None:
        metrics.print_summary()
