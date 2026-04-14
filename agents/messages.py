"""
logistics_mas/agents/messages.py

Protocolo de comunicación para AutoGen v0.4 (Actor Model).
Cada dataclass representa un tipo de mensaje que los agentes pueden procesar.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PickupRequest:
    """Enviado por VehicleAgent a DepotAgent para solicitar carga."""
    vehicle_id: str
    amount: int


@dataclass
class PickupResponse:
    """Enviado por DepotAgent a VehicleAgent con el resultado de la carga."""
    success: bool
    amount: int
    stock_left: int


@dataclass
class DeliveryMessage:
    """Enviado por VehicleAgent a ClientAgent al entregar mercancía."""
    vehicle_id: str
    depot_id: str
    amount: int


@dataclass
class DeliveryAck:
    """Enviado por ClientAgent a VehicleAgent confirmando la recepción."""
    success: bool
    delivered: int
    demand_left: int


@dataclass
class StatusReport:
    """Enviado por VehicleAgent a CoordinatorAgent con su estado actual."""
    vehicle_id: str
    state: str
    pos: Tuple[int, int]
    has_cargo: bool
    target_depot: Optional[str] = None
    target_client: Optional[str] = None


@dataclass
class Assignment:
    """Enviado por CoordinatorAgent a VehicleAgent para asignar una tarea."""
    depot_id: str
    client_id: str


@dataclass
class TickMessage:
    """
    Mensaje de control enviado por el motor de simulación (Scenario)
    a los VehicleAgents para sincronizar el avance por pasos.
    """
    iteration: int


@dataclass
class DemandAnnouncement:
    """Mensaje proactivo de los Clientes al inicio de la simulación."""
    client_id: str
    demand: dict[str, int]
