"""
scenarios/simple_scenario.py

Escenario 1: Vehículos independientes (sin coordinación centralizada).
Adaptado a AutoGen v0.4 asíncrono y AgentInstantiationContext.
"""
from __future__ import annotations
from .base_scenario import BaseScenario
from agents.vehicle_agent import VehicleAgent


class SimpleScenario(BaseScenario):
    SCENARIO_TYPE = "simple"

    @classmethod
    def from_json(cls, path: str) -> SimpleScenario:
        grid, depots_data, clients_data, vehicles_data, scenario_name = cls.load_scenario(path)
        return cls(grid, depots_data, clients_data, vehicles_data, scenario_name)

    def _create_vehicle_agent(self, vdata):
        return VehicleAgent(vdata, self.grid, self.depot_agents, self.client_agents)
