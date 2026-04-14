"""
scenarios/coordinated_scenario.py

Escenario 2: Coordinación centralizada mediante un CoordinatorAgent.
Adaptado a AutoGen v0.4 asíncrono y AgentInstantiationContext.
"""
from __future__ import annotations
from typing import List
from autogen_core import AgentId, AgentInstantiationContext

from .base_scenario import BaseScenario
from agents.coordinator_agent import CoordinatorAgent
from agents.vehicle_agent import VehicleAgent


class CoordinatedScenario(BaseScenario):
    SCENARIO_TYPE = "coordinated"

    def __init__(
        self,
        grid,
        depots_data,
        clients_data,
        vehicles_data,
        scenario_name,
    ):
        super().__init__(grid, depots_data, clients_data, vehicles_data, scenario_name)
        self.coordinator_agent: CoordinatorAgent = None

    @classmethod
    def from_json(cls, path: str) -> CoordinatedScenario:
        grid, depots_data, clients_data, vehicles_data, scenario_name = cls.load_scenario(path)
        return cls(grid, depots_data, clients_data, vehicles_data, scenario_name)

    async def _setup_runtime(self) -> None:
        """Registra agentes y al coordinador."""
        await super()._setup_runtime()
        
        # Factoría para el Coordinador (0 argumentos)
        def coordinator_factory():
            agent = CoordinatorAgent(self.depots_data, self.clients_data)
            self.coordinator_agent = agent
            return agent

        # Registrar Factoría
        await self.runtime.register_factory(
            type="CoordinatorAgent",
            agent_factory=coordinator_factory,
            expected_class=CoordinatorAgent
        )

    def _create_vehicle_agent(self, vdata):
        return VehicleAgent(vdata, self.grid, self.depot_agents, self.client_agents)

    async def _pre_tick(self) -> None:
        """Fase de coordinación: los vehículos reportan y el coordinador asigna."""
        coord_aid = AgentId("CoordinatorAgent", "central")
        # Aseguramos que el coordinador existe en el runtime (v0.4 lazy instantiation)
        await self.runtime.try_get_underlying_agent_instance(coord_aid, type=object)
        
        for va in self.vehicle_agents:
            report = va.get_status_report()
            await self.runtime.send_message(report, recipient=coord_aid)
        
        if self.coordinator_agent:
            await self.coordinator_agent.coordinate()

    def get_assignment_log(self) -> List[str]:
        return self.coordinator_agent.get_assignment_log() if self.coordinator_agent else []
