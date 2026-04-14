"""
core/entities.py
Dataclasses que representan los elementos del sistema logístico:
Depot, Client, Vehicle, Cargo, VehicleState.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def weight(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}[self.value]


class VehicleState(str, Enum):
    IDLE = "idle"
    HEADING_DEPOT = "heading_depot"
    HEADING_CLIENT = "heading_client"
    DELIVERING = "delivering"
    WAITING_RESPONSE = "waiting_response"


@dataclass
class Depot:
    id: str
    pos: Tuple[int, int]          # (row, col)
    inventory: int                 # unidades totales disponibles
    even_packages: int             # paquetes de tamaño par
    odd_packages: int              # paquetes de tamaño impar
    client_ids: List[str] = field(default_factory=list)

    def available(self) -> int:
        return self.inventory

    def withdraw(self, amount: int) -> int:
        """Retira hasta `amount` unidades. Devuelve la cantidad real retirada."""
        actual = min(amount, self.inventory)
        self.inventory -= actual
        return actual

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pos": list(self.pos),
            "inventory": self.inventory,
            "even_packages": self.even_packages,
            "odd_packages": self.odd_packages,
            "clients": self.client_ids,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Depot":
        return cls(
            id=d["id"],
            pos=tuple(d["pos"]),
            inventory=d["inventory"],
            even_packages=d["even_packages"],
            odd_packages=d["odd_packages"],
            client_ids=d.get("clients", []),
        )


@dataclass
class Client:
    id: str
    pos: Tuple[int, int]
    demand: Dict[str, int]         # {depot_id: units}
    priority: Priority

    def total_demand(self) -> int:
        return sum(self.demand.values())

    def pending_demand(self) -> int:
        return sum(v for v in self.demand.values() if v > 0)

    def receive(self, depot_id: str, amount: int) -> int:
        """Recibe `amount` del depósito indicado. Devuelve lo realmente recibido."""
        needed = self.demand.get(depot_id, 0)
        actual = min(needed, amount)
        self.demand[depot_id] = needed - actual
        return actual

    def is_satisfied(self) -> bool:
        return all(v <= 0 for v in self.demand.values())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pos": list(self.pos),
            "demand": dict(self.demand),
            "priority": self.priority.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Client":
        return cls(
            id=d["id"],
            pos=tuple(d["pos"]),
            demand={k: v for k, v in d["demand"].items()},
            priority=Priority(d["priority"]),
        )


@dataclass
class Cargo:
    """Mercancía que lleva un vehículo."""
    depot_id: str
    client_id: str
    units: int


@dataclass
class Vehicle:
    id: str
    pos: Tuple[int, int]
    capacity: int
    cost_per_step: float
    state: VehicleState = VehicleState.IDLE
    cargo: Optional[Cargo] = None
    target_depot: Optional[str] = None
    target_client: Optional[str] = None
    route: List[Tuple[int, int]] = field(default_factory=list)

    # Estadísticas acumuladas
    total_moves: int = 0
    total_cost: float = 0.0
    wasted_space: float = 0.0      # sum of (capacity - cargo) per step while en_route
    idle_ticks: int = 0            # ticks en estado IDLE
    total_deliveries: int = 0      # ENTREGAS COMPLETADAS

    def load(self, cargo: Cargo) -> None:
        self.cargo = cargo
        self.state = VehicleState.HEADING_CLIENT

    def unload(self) -> Optional[Cargo]:
        c = self.cargo
        self.cargo = None
        return c

    def current_load(self) -> int:
        return self.cargo.units if self.cargo else 0

    def free_space(self) -> int:
        return self.capacity - self.current_load()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pos": list(self.pos),
            "capacity": self.capacity,
            "cost_per_step": self.cost_per_step,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Vehicle":
        return cls(
            id=d["id"],
            pos=tuple(d["pos"]),
            capacity=d["capacity"],
            cost_per_step=float(d["cost_per_step"]),
        )
