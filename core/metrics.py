"""
core/metrics.py
Recoge y acumula métricas de simulación por iteración.
Exporta a JSON.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class VehicleMetrics:
    vehicle_id: str
    moves: int = 0
    deliveries: int = 0
    cost: float = 0.0
    wasted_space_steps: float = 0.0  # acumulado (capacity - cargo) cada step con carga
    idle_ticks: int = 0

    def to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "moves": self.moves,
            "deliveries": self.deliveries,
            "cost": round(self.cost, 4),
            "wasted_space_steps": round(self.wasted_space_steps, 4),
            "idle_ticks": self.idle_ticks,
        }


@dataclass
class SimulationMetrics:
    scenario_name: str
    scenario_type: str
    vehicle_metrics: Dict[str, VehicleMetrics] = field(default_factory=dict)
    total_iterations: int = 0

    def init_vehicle(self, vid: str) -> None:
        if vid not in self.vehicle_metrics:
            self.vehicle_metrics[vid] = VehicleMetrics(vehicle_id=vid)

    def reset(self) -> None:
        """Pone a cero todas las métricas acumuladas manteniendo los vehículos registrados."""
        self.total_iterations = 0
        for vm in self.vehicle_metrics.values():
            vm.moves = 0
            vm.deliveries = 0
            vm.cost = 0.0
            vm.wasted_space_steps = 0.0
            vm.idle_ticks = 0

    # ------------------------------------------------------------------
    # Acumuladores llamados por el motor en cada tick
    # ------------------------------------------------------------------

    def record_move(self, vid: str, cost: float) -> None:
        self.vehicle_metrics[vid].moves += 1
        self.vehicle_metrics[vid].cost += cost

    def record_delivery(self, vid: str) -> None:
        self.vehicle_metrics[vid].deliveries += 1

    def record_wasted_space(self, vid: str, capacity: int, cargo: int) -> None:
        """Registra espacio vacío en un paso donde el vehículo está cargado en ruta."""
        self.vehicle_metrics[vid].wasted_space_steps += max(0, capacity - cargo)

    def record_idle(self, vid: str) -> None:
        self.vehicle_metrics[vid].idle_ticks += 1

    def tick(self) -> None:
        self.total_iterations += 1

    # ------------------------------------------------------------------
    # Totales agregados
    # ------------------------------------------------------------------

    @property
    def total_moves(self) -> int:
        return sum(v.moves for v in self.vehicle_metrics.values())

    @property
    def total_cost(self) -> float:
        return sum(v.cost for v in self.vehicle_metrics.values())

    @property
    def total_wasted_space(self) -> float:
        return sum(v.wasted_space_steps for v in self.vehicle_metrics.values())

    @property
    def total_idle_capacity(self) -> int:
        """Suma de (capacity_vehículo × ticks_idle) — aproximación de capacidad ociosa."""
        return sum(v.idle_ticks for v in self.vehicle_metrics.values())

    @property
    def total_deliveries(self) -> int:
        return sum(v.deliveries for v in self.vehicle_metrics.values())

    # ------------------------------------------------------------------
    # Serialización JSON
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "metrics": {
                "total_iterations": self.total_iterations,
                "total_moves": self.total_moves,
                "total_deliveries": self.total_deliveries,
                "total_cost": round(self.total_cost, 4),
                "wasted_space_steps": round(self.total_wasted_space, 4),
                "total_idle_ticks": self.total_idle_capacity,
            },
            "vehicle_logs": [v.to_dict() for v in self.vehicle_metrics.values()],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"[Metrics] Resultado guardado en: {path}")

    def print_summary(self) -> None:
        d = self.to_dict()
        m = d["metrics"]
        print("\n" + "=" * 50)
        print(f"  RESUMEN — {self.scenario_type.upper()} ({self.scenario_name})")
        print("=" * 50)
        print(f"  Iteraciones totales   : {m['total_iterations']}")
        print(f"  Desplazamientos       : {m['total_moves']}")
        print(f"  Entregas completadas  : {m['total_deliveries']}")
        print(f"  Coste total           : {m['total_cost']:.2f}")
        print(f"  Espacio desperdiciado : {m['wasted_space_steps']:.2f} ud·paso")
        print(f"  Ticks en idle         : {m['total_idle_ticks']}")
        print("=" * 50)
        print("\n  Por vehículo:")
        for v in d["vehicle_logs"]:
            print(
                f"  {v['vehicle_id']:4s}  mov={v['moves']:4d}  "
                f"entregas={v['deliveries']:2d}  "
                f"coste={v['cost']:7.2f}  "
                f"idle={v['idle_ticks']:4d}"
            )
        print()
