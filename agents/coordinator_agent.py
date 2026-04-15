"""
agents/coordinator_agent.py

Agente Coordinador (Actor Model — AutoGen v0.4).
Centraliza la asignación de tareas mediante reportes de estado asíncronos.
"""
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING
from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId

from .messages import StatusReport, Assignment

if TYPE_CHECKING:
    from core.entities import Depot, Client


class CoordinatorAgent(RoutedAgent):
    """
    Agente que optimiza la flota asignando (Depósito -> Cliente).
    Evita que varios vehículos vayan a la misma tarea.
    """

    def __init__(
        self,
        depots: Dict[str, Depot],
        clients: Dict[str, Client],
    ) -> None:
        super().__init__("CoordinatorAgent")
        self._depots = depots
        self._clients = clients
        
        # Tareas actualmente asignadas: {vehicle_id: (depot_id, client_id, amount)}
        self.active_assignments: Dict[str, tuple] = {}
        # Reportes de estado recibidos en esta iteración
        self.current_reports: Dict[str, StatusReport] = {}
        # Log histórico de acciones para el visualizador
        self.log: List[str] = []
        
        # Seguimiento de estancamiento para revocar tareas (si no hay protocolo de cortesía)
        self.stagnation_counters: Dict[str, int] = {}
        self.last_positions: Dict[str, Tuple[int, int]] = {}

    # ------------------------------------------------------------------
    # Manejadores
    # ------------------------------------------------------------------

    @message_handler
    async def handle_status_report(self, message: StatusReport, ctx: MessageContext) -> None:
        """Recibe el estado de un vehículo."""
        vid = message.vehicle_id
        
        # Detección de estancamiento
        if vid in self.last_positions and self.last_positions[vid] == message.pos:
            if message.state != "idle":
                self.stagnation_counters[vid] = self.stagnation_counters.get(vid, 0) + 1
        else:
            self.stagnation_counters[vid] = 0
        
        self.last_positions[vid] = message.pos
        self.current_reports[vid] = message
        
        if message.state == "idle":
            self.stagnation_counters[vid] = 0
            self._cleanup_finished_tasks(vid)

    # ------------------------------------------------------------------
    # Lógica de asignación
    # ------------------------------------------------------------------

    async def coordinate(self) -> None:
        """
        Método invocado por el orquestador al inicio de cada Tick.
        Decide las mejores asignaciones para los vehículos en IDLE.
        """
        for vid, report in self.current_reports.items():
            # Limpieza robusta: si el vehículo está libre, liberamos asignación
            if report.state == "idle":
                self._cleanup_finished_tasks(vid)
            
            # REVOCACIÓN: Si el vehículo lleva > 15 turnos sin moverse y tiene tarea, se la quitamos
            if self.stagnation_counters.get(vid, 0) >= 15 and vid in self.active_assignments:
                task = self.active_assignments[vid]
                self.log.append(f"  Coordinador: REVOCADA tarea a {vid} por estancamiento en {report.pos}")
                del self.active_assignments[vid]
                self.stagnation_counters[vid] = 0
            
            if report.state == "idle":
                # Limpiar tareas terminadas si el vehículo reporta IDLE
                self._cleanup_finished_tasks(vid)
                
                # Buscar mejor tarea disponible considerando la capacidad reportada
                task_data = self._find_best_task(vid, report.capacity)
                if task_data:
                    depot_id, client_id, amount = task_data
                    self.active_assignments[vid] = (depot_id, client_id, amount)
                    
                    # Enviar mensaje de asignación con la cantidad exacta
                    vehicle_aid = AgentId(type="VehicleAgent", key=vid)
                    await self.send_message(
                        Assignment(depot_id, client_id, amount),
                        recipient=vehicle_aid
                    )
                    self.log.append(f"  Coordinador: {vid} → {depot_id}:{client_id} (uds: {amount})")

    def _find_best_task(self, vehicle_id: str, capacity: int) -> tuple | None:
        """
        Calcula el mejor par (Depósito, Cliente) y la cantidad óptima a transportar.
        """
        best_score = -1.0
        best_result = None

        for did, d in self._depots.items():
            if d.inventory <= 0: continue
            
            for cid, c in self._clients.items():
                if c.is_satisfied(): continue
                demand = c.demand.get(did, 0)
                if demand <= 0: continue
                
                # Colaboración: máximo 2 vehículos por tarea
                assigned_to_this = [task for task in self.active_assignments.values() if task[0] == did and task[1] == cid]
                if len(assigned_to_this) >= 2: continue
                
                # Descontar lo que ya está en camino para no sobre-asignar
                units_in_transit = sum(task[2] for task in assigned_to_this)
                effective_demand = demand - units_in_transit
                if effective_demand <= 0: continue

                # Cantidad óptima: lo que quepa o lo que falte
                amount = min(capacity, effective_demand)
                
                # Heurística: prioridad penalizada por vehículos ya asignados
                score = (c.priority.weight() * (effective_demand / 10.0)) / (len(assigned_to_this) + 1)
                
                if score > best_score:
                    best_score = score
                    best_result = (did, cid, amount)

        return best_result

    def _cleanup_finished_tasks(self, vehicle_id: str) -> None:
        """Elimina la tarea asignada si el vehículo ya está libre."""
        if vehicle_id in self.active_assignments:
            del self.active_assignments[vehicle_id]

    def get_assignment_log(self) -> List[str]:
        return self.log
