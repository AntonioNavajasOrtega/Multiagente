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
        
        # Tareas actualmente asignadas para evitar duplicidad: {(depot_id, client_id): vehicle_id}
        self.active_assignments: Dict[tuple, str] = {}
        # Reportes de estado recibidos en esta iteración
        self.current_reports: Dict[str, StatusReport] = {}
        # Log histórico de acciones para el visualizador
        self.log: List[str] = []

    # ------------------------------------------------------------------
    # Manejadores
    # ------------------------------------------------------------------

    @message_handler
    async def handle_status_report(self, message: StatusReport, ctx: MessageContext) -> None:
        """Recibe el estado de un vehículo."""
        self.current_reports[message.vehicle_id] = message
        # Si el vehículo está ocupado con una tarea que ya terminó, liberamos.
        if message.state == "idle":
            self._cleanup_finished_tasks(message.vehicle_id)

    # ------------------------------------------------------------------
    # Lógica de asignación
    # ------------------------------------------------------------------

    async def coordinate(self) -> None:
        """
        Método invocado por el orquestador al inicio de cada Tick.
        Decide las mejores asignaciones para los vehículos en IDLE.
        """
        for vid, report in self.current_reports.items():
            if report.state == "idle":
                # Buscar mejor tarea disponible
                best_task = self._find_best_task()
                if best_task:
                    depot_id, client_id = best_task
                    self.active_assignments[best_task] = vid
                    
                    # Enviar mensaje de asignación al vehículo
                    vehicle_aid = AgentId(type="VehicleAgent", key=vid)
                    await self.send_message(
                        Assignment(depot_id, client_id),
                        recipient=vehicle_aid
                    )
                    self.log.append(f"  Coordinador: {vid} → {depot_id}:{client_id}")

    def _find_best_task(self) -> tuple | None:
        """
        Algoritmo greedy global: busca la tarea con mayor (prioridad / distancia media).
        Solo considera tareas no asignadas actualmente.
        """
        best_score = -1.0
        best_pair = None

        for did, d in self._depots.items():
            if d.inventory <= 0: continue
            
            for cid, c in self._clients.items():
                if c.is_satisfied(): continue
                demand = c.demand.get(did, 0)
                if demand <= 0: continue
                
                # Evitar tareas ya asignadas
                if (did, cid) in self.active_assignments: continue
                
                # Heurística: prioridad
                priority_val = c.priority.weight()
                score = priority_val * (demand / 10.0)
                
                if score > best_score:
                    best_score = score
                    best_pair = (did, cid)

        return best_pair

    def _cleanup_finished_tasks(self, vehicle_id: str) -> None:
        """Elimina tareas de active_assignments si el vehículo ya está libre."""
        to_del = [k for k, v in self.active_assignments.items() if v == vehicle_id]
        for k in to_del:
            del self.active_assignments[k]

    def get_assignment_log(self) -> List[str]:
        return self.log
