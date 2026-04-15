"""
scenarios/base_scenario.py

Motor de simulación asíncrono (Actor Model — AutoGen v0.4).
Orquestador del AgentRuntime y sincronización de Ticks.
"""
from __future__ import annotations
import json
import asyncio
from typing import Dict, List, Set, TYPE_CHECKING
from autogen_core import SingleThreadedAgentRuntime, AgentId

from core.entities import Depot, Client, Vehicle, VehicleState
from core.environment import Grid
from core.metrics import SimulationMetrics
from agents.depot_agent import DepotAgent
from agents.client_agent import ClientAgent

if TYPE_CHECKING:
    from agents.vehicle_agent import VehicleAgent
    from simulation.visualizer import Visualizer

MAX_ITERATIONS = 10_000


class BaseScenario:
    SCENARIO_TYPE = "base"

    def __init__(
        self,
        grid: Grid,
        depots_data: Dict[str, Depot],
        clients_data: Dict[str, Client],
        vehicles_data: List[Vehicle],
        scenario_name: str,
    ):
        self.grid = grid
        self.depots_data = depots_data
        self.clients_data = clients_data
        self.vehicles_data_map = {v.id: v for v in vehicles_data}
        self.scenario_name = scenario_name
        self.metrics = SimulationMetrics(
            scenario_name=scenario_name,
            scenario_type=self.SCENARIO_TYPE,
        )
        
        # Runtime de AutoGen v0.4
        self.runtime = SingleThreadedAgentRuntime()
        
        # Referencias a instancias de agentes (pobladas por las factorías)
        self.vehicle_agents: List["VehicleAgent"] = []
        self.depot_agents: Dict[str, DepotAgent] = {}
        self.client_agents: Dict[str, ClientAgent] = {}
        
        # IDs para control
        self.depot_ids = list(depots_data.keys())
        self.client_ids = list(clients_data.keys())
        self.vehicle_ids = [v.id for v in vehicles_data]

        # Inicializar métricas de vehículos
        for vid in self.vehicle_ids:
            self.metrics.init_vehicle(vid)

    # ------------------------------------------------------------------
    # Bucle principal Asíncrono
    # ------------------------------------------------------------------

    async def run(self, verbose: bool = True, visualizer: Visualizer = None) -> SimulationMetrics:
        # 1. Registro de Factorías
        await self._setup_runtime()
        
        # Iniciar el runtime solo si no está corriendo
        try:
            self.runtime.start()
        except RuntimeError:
            pass # Ya está corriendo

        # Forzar la creación de instancias mediante el runtime (dispara las factorías)
        # IMPORTANTE: Depósitos y Clientes primero para que los Vehículos tengan acceso a sus referencias
        for did in self.depot_ids:
            await self.runtime.try_get_underlying_agent_instance(AgentId("DepotAgent", did), type=object)
        for cid in self.client_ids:
            await self.runtime.try_get_underlying_agent_instance(AgentId("ClientAgent", cid), type=object)
        for vid in self.vehicle_ids:
            await self.runtime.try_get_underlying_agent_instance(AgentId("VehicleAgent", vid), type=object)

        if verbose:
            print(f"\n[{self.SCENARIO_TYPE.upper()}] Inicio: {self.scenario_name}")
            self._announce_demands(verbose)

        # 2. Bucle de Ticks
        for i in range(MAX_ITERATIONS):
            if self._all_delivered():
                break
            
            if visualizer and verbose:
                visualizer.print_grid(self.grid, self.vehicle_agents, self.metrics.total_iterations)
                visualizer.print_vehicle_status(self.vehicle_agents)
                await asyncio.sleep(0.05)

            await self._pre_tick()
            await self._tick()
            await self._post_tick()
            
            # CRITICAL: Yield control to allow the SingleThreadedAgentRuntime 
            # to process the message queue between ticks.
            await asyncio.sleep(0)
            
            self.metrics.tick()

            if verbose and not visualizer and self.metrics.total_iterations % 50 == 0:
                print(f"  Iter {self.metrics.total_iterations:4d} | entregas={self.metrics.total_deliveries}")
        
        # No paramos el runtime si queremos reusar agentes (ej en RL pretrain)
        # self.runtime.stop() 
        return self.metrics

    async def _setup_runtime(self) -> None:
        """Registra las factorías de agentes en el runtime v0.4."""
        if hasattr(self, "_runtime_initialized") and self._runtime_initialized:
            return

        from autogen_core import AgentInstantiationContext

        def depot_factory():
            aid = AgentInstantiationContext.current_agent_id()
            data = self.depots_data[aid.key]
            agent = DepotAgent(data)
            self.depot_agents[aid.key] = agent
            return agent

        await self.runtime.register_factory(
            type="DepotAgent",
            agent_factory=depot_factory,
            expected_class=DepotAgent
        )

        def client_factory():
            aid = AgentInstantiationContext.current_agent_id()
            data = self.clients_data[aid.key]
            agent = ClientAgent(data)
            self.client_agents[aid.key] = agent
            return agent

        await self.runtime.register_factory(
            type="ClientAgent",
            agent_factory=client_factory,
            expected_class=ClientAgent
        )

        def vehicle_factory():
            aid = AgentInstantiationContext.current_agent_id()
            data = self.vehicles_data_map[aid.key]
            agent = self._create_vehicle_agent(data)
            self.vehicle_agents.append(agent)
            return agent

        await self.runtime.register_factory(
            type="VehicleAgent",
            agent_factory=vehicle_factory,
            expected_class=self._get_vehicle_class()
        )
        self._runtime_initialized = True

    def reset_entities(self, depots_data: Dict[str, Depot], clients_data: Dict[str, Client], vehicles_data: List[Vehicle]):
        """Restaura el estado de todos los entes sin recrear los agentes."""
        self.depots_data = depots_data
        self.clients_data = clients_data
        self.vehicles_data_map = {v.id: v for v in vehicles_data}
        
        # Resetear datos internos de agentes existentes
        for did, agent in self.depot_agents.items():
            agent._depot = depots_data[did]
            
        for cid, agent in self.client_agents.items():
            agent._cli = clients_data[cid]
            
        for va in self.vehicle_agents:
            v_orig = self.vehicles_data_map[va.vehicle.id]
            va.vehicle.pos = v_orig.pos
            va.vehicle.state = v_orig.state
            va.vehicle.cargo = None
            va.vehicle.route = []
            va.vehicle.target_depot = None
            va.vehicle.target_client = None
            # IMPORTANTE: Resetear estadísticas acumuladas para separar entrenamiento de test
            va.vehicle.total_moves = 0
            va.vehicle.total_cost = 0.0
            va.vehicle.wasted_space = 0.0
            va.vehicle.idle_ticks = 0
            va.vehicle.total_deliveries = 0

        # Resetear métricas usando el nuevo método
        self.metrics.reset()

    def _get_vehicle_class(self):
        from agents.vehicle_agent import VehicleAgent
        return VehicleAgent

    def _create_vehicle_agent(self, vdata: Vehicle) -> "VehicleAgent":
        from agents.vehicle_agent import VehicleAgent
        return VehicleAgent(vdata, self.grid, self.depots_data, self.clients_data)

    async def _tick(self) -> None:
        # Usamos las referencias directas guardadas por la factoría
        agents = self.vehicle_agents
        occupied = {va.vehicle.pos for va in agents}
        for va in agents:
            occupied.discard(va.vehicle.pos)
            await va.step(self.metrics, occupied)
            occupied.add(va.vehicle.pos)
            
        # Sincronizar entregas asíncronas registradas en los vehículos con el objeto metrics
        for va in self.vehicle_agents:
            v = va.vehicle
            # Si el vehículo ha incrementado sus entregas en los manejadores asíncronos,
            # lo reflejamos en el objeto de métricas centralizado.
            while v.total_deliveries > self.metrics.vehicle_metrics[v.id].deliveries:
                self.metrics.record_delivery(v.id)

    async def _pre_tick(self) -> None:
        pass

    async def _post_tick(self) -> None:
        pass

    def _announce_demands(self, verbose: bool) -> None:
        if not verbose: return
        print("\n[Demanda inicial de clientes]")
        for ca in self.client_agents.values():
            print(f"  {ca.client_id}: {ca.demand_message()}")

    def _all_delivered(self) -> bool:
        satisfied_states = {ca.client_id: ca.is_satisfied() for ca in self.client_agents.values()}
        # Devolver True solo si todos están satisfechos
        all_sat = all(satisfied_states.values())
        
        # Si no han terminado y estamos en verbose, mostrar quién falta cada 100 pasos
        if not all_sat and self.metrics.total_iterations % 100 == 0:
            pending = []
            for cid, agent in self.client_agents.items():
                if not agent.is_satisfied():
                    pending.append(f"{cid}({agent.demand_message()})")
            if pending:
                print(f"  [DEBUG-TERMINATION] Esperando a clientes: {', '.join(pending)}")
                
        return all_sat

    @classmethod
    def load_scenario(cls, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        grid = Grid.from_dict(data["grid"])
        depots_data = {d["id"]: Depot.from_dict(d) for d in data["depots"]}
        clients_data = {c["id"]: Client.from_dict(c) for c in data["clients"]}
        vehicles_data = [Vehicle.from_dict(v) for v in data["vehicles"]]
        scenario_name = data.get("scenario_name", "unnamed")
        return grid, depots_data, clients_data, vehicles_data, scenario_name
