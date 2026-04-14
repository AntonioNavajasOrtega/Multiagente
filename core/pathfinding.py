"""
core/pathfinding.py
Algoritmo A* adaptado para 8 direcciones con penalizaciones de tráfico.
Heurística: distancia octil (Chebyshev) para movimiento en 8 dirs.
"""
from __future__ import annotations
import heapq
from typing import Dict, List, Optional, Tuple

from core.environment import Grid


def _octile_distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Heurística octil para movimiento en 8 direcciones."""
    dr = abs(a[0] - b[0])
    dc = abs(a[1] - b[1])
    return max(dr, dc) + (2**0.5 - 1) * min(dr, dc)


def astar(
    grid: Grid,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    vehicle_cost: float = 1.0,
    blocked: Optional[set] = None,
) -> List[Tuple[int, int]]:
    """
    Retorna la lista de posiciones (sin incluir start, incluyendo goal)
    que forman el camino óptimo. Lista vacía si no hay camino.

    blocked: conjunto de posiciones adicionales no transitables (otros vehículos).
    """
    if blocked is None:
        blocked = set()

    if start == goal:
        return []

    # Cola de prioridad: (f, g, pos)
    open_heap: List[Tuple[float, float, Tuple[int, int]]] = []
    h0 = _octile_distance(start, goal)
    heapq.heappush(open_heap, (h0, 0.0, start))

    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    g_cost: Dict[Tuple[int, int], float] = {start: 0.0}

    while open_heap:
        _, g, current = heapq.heappop(open_heap)

        if current == goal:
            # Reconstruir camino
            path = []
            node: Optional[Tuple[int, int]] = current
            while node != start:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        if g > g_cost.get(current, float("inf")):
            continue  # nodo desactualizado

        for neighbor in grid.neighbors(current):
            if neighbor in blocked and neighbor != goal:
                continue
            step_cost = grid.move_cost(neighbor, vehicle_cost)
            new_g = g_cost[current] + step_cost
            if new_g < g_cost.get(neighbor, float("inf")):
                g_cost[neighbor] = new_g
                came_from[neighbor] = current
                h = _octile_distance(neighbor, goal)
                heapq.heappush(open_heap, (new_g + h, new_g, neighbor))

    return []  # Sin camino


def find_path(
    grid: Grid,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    vehicle_cost: float = 1.0,
    blocked: Optional[set] = None,
) -> List[Tuple[int, int]]:
    """Interfaz pública del pathfinder."""
    return astar(grid, start, goal, vehicle_cost, blocked)


class AStar:
    """Clase envoltorio para el algoritmo A*."""
    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def find_path(
        self, 
        start: Tuple[int, int], 
        goal: Tuple[int, int], 
        blocked: Optional[set] = None
    ) -> List[Tuple[int, int]]:
        return find_path(self.grid, start, goal, blocked=blocked)
