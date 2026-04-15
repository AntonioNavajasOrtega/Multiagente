"""
agents/vehicle_agent.py

Agente Vehículo (Actor Model — AutoGen v0.4).
Planifica rutas y se comunica asíncronamente con depósitos, clientes y coordinador.
"""
from __future__ import annotations
import random
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId

from core.entities import Vehicle, VehicleState, Cargo, Priority, Depot, Client
from core.pathfinding import AStar
from .messages import (
    PickupRequest, PickupResponse, 
    DeliveryMessage, DeliveryAck,
    StatusReport, Assignment, TickMessage
)

if TYPE_CHECKING:
    from core.environment import Grid
    from core.metrics import SimulationMetrics


class VehicleAgent(RoutedAgent):
    """
    Agente Vehículo Autónomo.
    Maneja su estado y toma decisiones de movimiento en cada Tick.
    """

    def __init__(
        self,
        vehicle: Vehicle,
        grid: Grid,
        depots: Dict[str, Depot],
        clients: Dict[str, Client],
    ) -> None:
        super().__init__("VehicleAgent")
        self.vehicle = vehicle
        self.grid = grid
        self.depots = depots    # id -> Depot (Data)
        self.clients = clients  # id -> Client (Data)
        self.astar = AStar(grid)
        self.assigned_amount = 0  
        self.stagnation_counter = 0
        self.last_pos = vehicle.pos

    # ------------------------------------------------------------------
    # Manejadores de Mensajes
    # ------------------------------------------------------------------

    @message_handler
    async def handle_assignment(self, message: Assignment, ctx: MessageContext) -> None:
        """Recibe una tarea del coordinador."""
        # Aceptamos la tarea siempre que venga del coordinador (aunque no estemos IDLE,
        # esto permite re-asignaciones forzosas o revocaciones).
        self.vehicle.target_depot = message.depot_id
        self.vehicle.target_client = message.client_id
        self.assigned_amount = message.amount  # Guardamos la cantidad exacta
        self.vehicle.state = VehicleState.HEADING_DEPOT
        self.vehicle.route = []
        # Responder aceptación
        if ctx.sender:
            await self.send_message("ACCEPTED", recipient=ctx.sender)

    @message_handler
    async def handle_tick(self, message: TickMessage, ctx: MessageContext) -> None:
        """
        Disparado por el motor en cada paso de simulación.
        Este es el 'corazón' del agente.
        """
        # Nota: el 'occupied' se gestionará en el motor para evitar choques físicos,
        # pero aquí el agente decide su intención de movimiento.
        pass # La lógica real se implementa en el método step() invocado por el motor

    # ------------------------------------------------------------------
    # Lógica de Decisión (Step)
    # ------------------------------------------------------------------

    async def step(self, metrics: SimulationMetrics, occupied: Set[Tuple[int, int]]) -> None:
        """
        Lógica ejecutada en cada iteración.
        Ahora es asíncrona para permitir peticiones request/response.
        """
        v = self.vehicle
        
        # 0. Si estamos esperando respuesta asíncrona, no hacemos nada este tick
        if v.state == VehicleState.WAITING_RESPONSE:
            return

        # Detección de estancamiento (si no somos IDLE)
        if v.state != VehicleState.IDLE:
            if v.pos == self.last_pos:
                self.stagnation_counter += 1
            else:
                self.stagnation_counter = 0
            
            # Auto-Aborto tras 20 ticks bloqueado
            if self.stagnation_counter >= 20:
                print(f"  [STAGNATION] {v.id} aborta tarea en {v.pos} por bloqueo.")
                v.state = VehicleState.IDLE
                v.target_depot = None
                v.target_client = None
                v.route = []
                self.assigned_amount = 0
                self.stagnation_counter = 0
                return
        
        self.last_pos = v.pos

        if v.state == VehicleState.IDLE:
            # En modo simple (sin coordinador), buscamos tarea localmente
            target = self._find_random_task()
            if target:
                did, cid = target
                v.target_depot = did
                v.target_client = cid
                
                # Calcular cantidad necesaria para no desperdiciar stock
                client_obj = self.clients[cid]
                demand_dict = client_obj._cli.demand if hasattr(client_obj, "_cli") else client_obj.demand
                pending_demand = demand_dict.get(did, 0)
                self.assigned_amount = min(v.capacity, pending_demand)
                
                v.state = VehicleState.HEADING_DEPOT
                v.route = []
            else:
                metrics.record_idle(v.id)
            return

        # 1. Asegurar que tenemos ruta
        target_pos = self._get_target_pos()
        if target_pos and (not v.route or v.route[-1] != target_pos):
            v.route = self.astar.find_path(v.pos, target_pos, occupied)

        # 2. Intentar mover
        if v.route:
            next_pos = v.route[0]
            if next_pos not in occupied:
                v.pos = v.route.pop(0)
                # El método move_cost ya aplica el coste del vehículo
                total_step_cost = self.grid.move_cost(v.pos, v.cost_per_step)
                metrics.record_move(v.id, total_step_cost)
                if v.cargo:
                    metrics.record_wasted_space(v.id, v.capacity, v.cargo.units)
            else:
                # Celda ocupada, esperamos
                metrics.record_move(v.id, 0) # tick gastado sin mover

        # 3. Acciones al llegar a destino
        if v.pos == target_pos:
            if v.state == VehicleState.HEADING_DEPOT:
                # Recalcular asignación por si la demanda bajó mientras viajábamos
                did, cid = v.target_depot, v.target_client
                if did and cid:
                    client_obj = self.clients[cid]
                    demand_dict = client_obj._cli.demand if hasattr(client_obj, "_cli") else client_obj.demand
                    pending_demand = demand_dict.get(did, 0)
                    
                    # Si ya no hay demanda (otro vehículo llegó antes), abortar pickup
                    if pending_demand <= 0:
                        v.state = VehicleState.IDLE
                        v.target_depot = None
                        v.target_client = None
                        v.route = []
                        return

                    self.assigned_amount = min(self.assigned_amount if self.assigned_amount > 0 else v.capacity, pending_demand)

                await self._perform_pickup(v.target_depot, metrics)
            elif v.state == VehicleState.HEADING_CLIENT:
                await self._perform_delivery(v.target_client, metrics)

    # ------------------------------------------------------------------
    # Interacciones Asíncronas (Actor style)
    # ------------------------------------------------------------------

    async def _perform_pickup(self, depot_id: str, metrics: SimulationMetrics) -> None:
        """Solicita carga al depósito mediante REQUEST/RESPONSE."""
        v = self.vehicle
        # Usamos la cantidad asignada por el coordinador para no vaciar el depósito sin necesidad
        amount = self.assigned_amount if self.assigned_amount > 0 else v.capacity 
        
        # En v0.4 usamos AgentId para localizar al DepotAgent
        depot_aid = AgentId(type="DepotAgent", key=depot_id)
        
        # Pasar a estado de espera antes de enviar para evitar re-envíos en el siguiente tick
        v.state = VehicleState.WAITING_RESPONSE
        print(f"  [MSG] {v.id} -> {depot_id}: PickupRequest(units={amount})")
        await self.send_message(PickupRequest(v.id, amount), recipient=depot_aid)

    @message_handler
    async def handle_pickup_response(self, message: PickupResponse, ctx: MessageContext) -> None:
        """Manejador para la respuesta del depósito."""
        v = self.vehicle
        if message.success:
            v.cargo = Cargo(v.target_depot, v.target_client, message.amount)
            v.state = VehicleState.HEADING_CLIENT
            v.route = []
            # print(f"  [DEBUG] {v.id} cargado con {message.amount} de {v.target_depot}")
        else:
            # Si nos deniegan (sin stock), volvemos a IDLE para buscar otra cosa
            v.state = VehicleState.IDLE
            v.target_depot = None
            v.target_client = None

    async def _perform_delivery(self, client_id: str, metrics: SimulationMetrics) -> None:
        """Entrega mercancía al cliente."""
        v = self.vehicle
        if not v.cargo: return
        
        client_aid = AgentId(type="ClientAgent", key=client_id)
        
        # Pasar a estado de espera antes de enviar
        v.state = VehicleState.WAITING_RESPONSE
        print(f"  [MSG] {v.id} -> {client_id}: DeliveryMessage(units={v.cargo.units})")
        await self.send_message(
            DeliveryMessage(v.id, v.cargo.depot_id, v.cargo.units),
            recipient=client_aid
        )

    @message_handler
    async def handle_delivery_ack(self, message: DeliveryAck, ctx: MessageContext) -> None:
        """Confirma la recepción por parte del cliente."""
        v = self.vehicle
        if message.success:
            # CRITICAL: Registrar la entrega en las métricas
            # Necesitamos acceso a metrics, pero este es un manejador de mensajes asíncrono.
            # Los manejadores no reciben 'metrics'. 
            # Una solución es que el motor (BaseScenario) extraiga estas métricas al final,
            # pero para compatibilidad con el diseño actual, seguiremos usando el objeto metrics
            # si lo guardamos o lo pasamos.
            # Sin embargo, 'metrics' se pasa a 'step()', no a los manejadores.
            
            # Ajuste: El objeto 'metrics' debe ser accesible globalmente o por referencia.
            # En v0.4 lo correcto es que el agente guarde su contador y el motor lo recoja.
            # Por ahora, incrementaremos un contador interno en el objeto Vehicle entity.
            v.total_deliveries += 1
            v.cargo = None
            v.state = VehicleState.IDLE
            v.target_depot = None
            v.target_client = None
            v.route = []
            # print(f"  [DEBUG] {v.id} entrega completada en {ctx.sender}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_random_task(self) -> Optional[Tuple[str, str]]:
        """
        Búsqueda simple (Greedy): busca depósitos con stock y clientes con demanda hacia ellos.
        """
        possible_pairs = []
        for did, da in self.depots.items():
            if da.is_empty(): continue
            for cid, ca in self.clients.items():
                if ca.is_satisfied(): continue
                if ca.has_demand_from(did):
                    possible_pairs.append((did, cid))
        
        if not possible_pairs:
            return None
        
        # Mezclar para aleatoriedad
        return random.choice(possible_pairs)

    def _get_target_pos(self) -> Optional[Tuple[int, int]]:
        v = self.vehicle
        if v.state == VehicleState.HEADING_DEPOT and v.target_depot:
            return self.depots[v.target_depot].pos
        if v.state == VehicleState.HEADING_CLIENT and v.target_client:
            return self.clients[v.target_client].pos
        return None

    def get_status_report(self) -> StatusReport:
        v = self.vehicle
        return StatusReport(
            vehicle_id=v.id,
            state=v.state.value,
            pos=v.pos,
            has_cargo=(v.cargo is not None),
            target_depot=v.target_depot,
            target_client=v.target_client,
            capacity=v.capacity
        )
