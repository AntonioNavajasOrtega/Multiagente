"""
scenarios/rl_scenario.py

Escenario 3: Aprendizaje por Refuerzo (Q-Learning) asíncrono.
Adaptado a AutoGen v0.4 y AgentInstantiationContext.
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, TYPE_CHECKING
from autogen_core import AgentId, AgentInstantiationContext

from .base_scenario import BaseScenario
from agents.rl_vehicle_agent import RLVehicleAgent

if TYPE_CHECKING:
    from core.environment import Grid


class RLScenario(BaseScenario):
    SCENARIO_TYPE = "rl"

    def __init__(
        self,
        grid,
        depots_data,
        clients_data,
        vehicles_data,
        scenario_name,
        epsilon=0.3,
        alpha=0.1,
        gamma=0.9
    ):
        super().__init__(grid, depots_data, clients_data, vehicles_data, scenario_name)
        self.epsilon = epsilon
        self.alpha = alpha
        self.gamma = gamma

    @classmethod
    def from_json(
        cls, 
        path: str, 
        epsilon: float = 0.3, 
        alpha: float = 0.1, 
        gamma: float = 0.9
    ) -> RLScenario:
        grid, depots_data, clients_data, vehicles_data, scenario_name = cls.load_scenario(path)
        return cls(grid, depots_data, clients_data, vehicles_data, scenario_name, epsilon, alpha, gamma)

    def _create_vehicle_agent(self, vdata):
        return RLVehicleAgent(
            vdata, self.grid, self.depot_agents, self.client_agents,
            epsilon=self.epsilon, alpha=self.alpha, gamma=self.gamma
        )

    def _get_vehicle_class(self):
        return RLVehicleAgent

    async def pretrain(self, episodes: int, scenario_path: str, verbose: bool = False) -> None:
        """Entrena los agentes ejecutan la simulación varias veces."""
        if verbose:
            print(f"\n[RL] Iniciando pre-entrenamiento: {episodes} episodios")
        
        # Debemos asegurar que los agentes están creados antes de manipularlos
        await self._setup_runtime()
        for vid in self.vehicle_ids:
            await self.runtime.try_get_underlying_agent_instance(AgentId("VehicleAgent", vid), type=object)

        orig_epsilon = [va.epsilon for va in self.vehicle_agents]
        
        for ep in range(episodes):
            grid, depots_data, clients_data, vehicles_data, _ = self.load_scenario(scenario_path)
            
            # Reseteamos el estado de TODA la simulación (entidades y vehículos)
            self.reset_entities(depots_data, clients_data, vehicles_data)
            
            # Decaimiento programado de epsilon
            for i, va in enumerate(self.vehicle_agents):
                va.epsilon = max(0.05, orig_epsilon[i] * (1 - ep/episodes))

            await self.run(verbose=False)
            
            if verbose and (ep + 1) % 5 == 0:
                print(f"  Episodio {ep + 1}/{episodes} completado.")

        # CRITICAL: Al finalizar el entrenamiento, dejamos el escenario listo para la ejecución oficial
        grid, depots_data, clients_data, vehicles_data, _ = self.load_scenario(scenario_path)
        self.reset_entities(depots_data, clients_data, vehicles_data)
        if verbose:
            print("[RL] Entrenamiento completado. Escenario reseteado para ejecución final.")

    def get_rl_stats(self) -> dict:
        return {
            "agents": [
                {
                    "vehicle_id": va.vehicle.id,
                    "q_table_states": len(va.q_table),
                    "epsilon": round(va.epsilon, 4)
                }
                for va in self.vehicle_agents
            ]
        }
