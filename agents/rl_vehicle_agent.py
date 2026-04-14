"""
agents/rl_vehicle_agent.py

Extensión de VehicleAgent que usa Q-Learning para decidir movimientos.
Adaptado a AutoGen v0.4 (Actor Model).
"""
from __future__ import annotations
import random
import numpy as np
from typing import Dict, List, Set, Tuple, TYPE_CHECKING
from autogen_core import message_handler, MessageContext

from .vehicle_agent import VehicleAgent
from core.entities import VehicleState

if TYPE_CHECKING:
    from core.metrics import SimulationMetrics


class RLVehicleAgent(VehicleAgent):
    """
    Vehículo que aprende la ruta óptima mediante Q-Learning.
    Mantiene la misma interfaz de comunicación por mensajes que VehicleAgent.
    """

    def __init__(
        self,
        vehicle: Vehicle, 
        grid: Grid, 
        depots: Dict[str, Depot], 
        clients: Dict[str, Client],
        epsilon: float = 0.3,
        alpha: float = 0.1,
        gamma: float = 0.9,
    ) -> None:
        super().__init__(vehicle, grid, depots, clients)
        self._type_name = "RLVehicleAgent"
        
        # Parámetros RL
        self.epsilon = epsilon
        self.alpha = alpha
        self.gamma = gamma
        
        # Q-Table: {(state_key): {action_idx: q_value}}
        # State: (pos_r, pos_c, has_cargo, target_r, target_c)
        self.q_table: Dict[Tuple, np.ndarray] = {}
        
        # Acciones: 8 direcciones + esperar (idx 0-8)
        self.actions = [
            (-1, 0), (1, 0), (0, -1), (0, 1),   # N, S, E, O
            (-1, -1), (-1, 1), (1, -1), (1, 1), # Diagonales
            (0, 0)                              # Esperar
        ]

    # ------------------------------------------------------------------
    # Lógica RL
    # ------------------------------------------------------------------

    async def step(self, metrics: SimulationMetrics, occupied: Set[Tuple[int, int]]) -> None:
        """
        Sobreescribe la toma de decisiones con la política epsilon-greedy.
        """
        v = self.vehicle

        if v.state == VehicleState.WAITING_RESPONSE:
            return
            
        if v.state == VehicleState.IDLE:
            # INTEGRACIÓN: Al igual que el agente base, el agente RL debe buscar tareas si está IDLE
            target = self._find_random_task()
            if target:
                did, cid = target
                v.target_depot = did
                v.target_client = cid
                v.state = VehicleState.HEADING_DEPOT
                v.route = []
            else:
                metrics.record_idle(v.id)
            return

        target_pos = self._get_target_pos()
        if not target_pos: return

        # 1. Obtener estado actual
        state = self._get_state(v.pos, target_pos)
        
        # 2. Elegir acción
        action_idx = self._choose_action(state, target_pos)
        move = self.actions[action_idx]
        next_pos = (v.pos[0] + move[0], v.pos[1] + move[1])

        # 3. Ejecutar y obtener recompensa
        reward = -1.0 # Coste base por paso
        
        # Validar movimiento (límites y obstáculos)
        can_move = (
            self.grid.is_passable(next_pos) and 
            next_pos not in occupied
        )

        if can_move:
            v.pos = next_pos
            # El método move_cost ya aplica la penalización de tráfico y el coste base
            total_step_cost = self.grid.move_cost(v.pos, v.cost_per_step)
            
            # Recompensa RL (penalizada por el coste del paso)
            reward -= (total_step_cost - v.cost_per_step) 
            
            if v.pos == target_pos:
                # RECOMPENSA BASADA EN PRIORIDAD: mayor peso si el cliente es alta prioridad
                priority_bonus = 50.0
                if v.state == VehicleState.HEADING_CLIENT and v.target_client in self.clients:
                    priority = self.clients[v.target_client]._cli.priority
                    priority_bonus *= priority.weight()  # HIGH=3, MEDIUM=2, LOW=1
                
                reward += priority_bonus
            
            metrics.record_move(v.id, total_step_cost)
            if v.cargo:
                metrics.record_wasted_space(v.id, v.capacity, v.cargo.units)
        else:
            # Si intenta chocar o salir, penalizar y no mover
            if move != (0, 0): reward -= 5.0
            next_pos = v.pos
            metrics.record_move(v.id, 0)

        # 4. Actualizar Q-Table
        next_state = self._get_state(next_pos, target_pos)
        self._update_q(state, action_idx, reward, next_state)

        # 5. Acciones de llegada (mensajes asíncronos)
        if v.pos == target_pos:
            if v.state == VehicleState.HEADING_DEPOT:
                await self._perform_pickup(v.target_depot, metrics)
            elif v.state == VehicleState.HEADING_CLIENT:
                await self._perform_delivery(v.target_client, metrics)

    # ------------------------------------------------------------------
    # Implementación matemática Q-Learning
    # ------------------------------------------------------------------

    def _get_state(self, pos: Tuple[int, int], target: Tuple[int, int]) -> Tuple:
        return (pos[0], pos[1], self.vehicle.cargo is not None, target[0], target[1])

    def _choose_action(self, state: Tuple, target: Tuple[int, int]) -> int:
        # Inicializar si el estado es nuevo
        if state not in self.q_table:
            self.q_table[state] = np.zeros(len(self.actions))
            # Respaldo: si no conocemos el estado, seguir A*
            path = self.astar.find_path(self.vehicle.pos, target, set())
            if path:
                next_step = path[0]
                move = (next_step[0] - self.vehicle.pos[0], next_step[1] - self.vehicle.pos[1])
                try:
                    return self.actions.index(move)
                except ValueError: return 8
            return 8 # Esperar

        if random.random() < self.epsilon:
            return random.randint(0, len(self.actions) - 1)
        
        return int(np.argmax(self.q_table[state]))

    def _update_q(self, state: Tuple, action: int, reward: float, next_state: Tuple) -> None:
        if next_state not in self.q_table:
            self.q_table[next_state] = np.zeros(len(self.actions))
        
        best_next = np.max(self.q_table[next_state])
        current_q = self.q_table[state][action]
        
        # Fórmula Bellman: Q = Q + α * (R + γ * max(Q') - Q)
        self.q_table[state][action] += self.alpha * (reward + self.gamma * best_next - current_q)
