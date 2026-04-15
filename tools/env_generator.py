"""
tools/env_generator.py

Generador de entornos de simulación.
Modos:
  - Interactivo (--interactive): pide datos por consola
  - Parametrizado (por argumentos): generación automática con seed reproducible
  - Resultado: JSON del entorno guardado en el fichero de salida
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from typing import List, Tuple


# ------------------------------------------------------------------
# Helpers de generación
# ------------------------------------------------------------------

def _make_empty_grid(rows: int, cols: int) -> List[List[str]]:
    return [["." for _ in range(cols)] for _ in range(rows)]


def _random_free_pos(
    grid: List[List[str]], rows: int, cols: int, taken: set
) -> Tuple[int, int]:
    """Devuelve una posición libre aleatoria que no esté en `taken`."""
    attempts = 0
    while attempts < 2000:
        r, c = random.randint(0, rows - 1), random.randint(0, cols - 1)
        if grid[r][c] == "." and (r, c) not in taken:
            return (r, c)
        attempts += 1
    raise RuntimeError("No se encontró posición libre en el grid. Reduce obstáculos.")


def is_connected(grid, rows, cols, points):
    """
    Verifica que todos los puntos en `points` estén en el mismo componente conexo 
    usando BFS. Los obstáculos '#' bloquean el paso.
    """
    if not points: return True
    
    start = points[0]
    queue = [start]
    visited = {start}
    
    reachable_count = 0
    targets = set(points)
    
    while queue:
        r, c = queue.pop(0)
        if (r, c) in targets:
            reachable_count += 1
        
        # 4 direcciones
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] != "#" and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append((nr, nc))
    
    return reachable_count == len(targets)


# ------------------------------------------------------------------
# Generación automática
# ------------------------------------------------------------------

def generate_scenario(
    rows: int,
    cols: int,
    num_depots: int,
    num_clients: int,
    num_vehicles: int,
    num_obstacles: int,
    num_traffic: int,
    depot_inventory: int,
    client_demand: int,
    vehicle_capacity: int,
    vehicle_cost: float,
    traffic_penalty: float,
    scenario_name: str,
    seed: int,
) -> dict:
    random.seed(seed)
    
    # Intentar generar un mapa conectado (máximo 100 intentos)
    for attempt in range(100):
        grid = _make_empty_grid(rows, cols)
        taken: set = set()
        all_important_points = [] # Depósitos, Clientes, Vehículos

        try:
            # 1. Obstáculos
            for _ in range(num_obstacles):
                r, c = _random_free_pos(grid, rows, cols, taken)
                grid[r][c] = "#"
                taken.add((r, c))

            # 2. Zonas de tráfico
            for _ in range(num_traffic):
                r, c = _random_free_pos(grid, rows, cols, taken)
                grid[r][c] = "T"
                taken.add((r, c))

            # 3. Depósitos
            depots = []
            for i in range(num_depots):
                r, c = _random_free_pos(grid, rows, cols, taken)
                grid[r][c] = "D"
                taken.add((r, c))
                all_important_points.append((r, c))
                even_pkg = random.randint(1, depot_inventory // 4 + 1)
                odd_pkg = random.randint(1, depot_inventory // 4 + 1)
                depots.append({
                    "id": f"D{i}",
                    "pos": [r, c],
                    "inventory": depot_inventory,
                    "even_packages": even_pkg,
                    "odd_packages": odd_pkg,
                    "clients": [],
                })

            # 4. Clientes
            clients = []
            priorities = ["high", "medium", "low"]
            for i in range(num_clients):
                r, c = _random_free_pos(grid, rows, cols, taken)
                grid[r][c] = "C"
                taken.add((r, c))
                all_important_points.append((r, c))
                # Asignar demanda a 1 o 2 depósitos al azar
                n_depots_for_client = min(num_depots, random.randint(1, 2))
                selected_depots = random.sample(range(num_depots), n_depots_for_client)
                demand = {}
                for di in selected_depots:
                    demand[f"D{di}"] = random.randint(1, client_demand)
                    depots[di]["clients"].append(f"C{i}")

                clients.append({
                    "id": f"C{i}",
                    "pos": [r, c],
                    "demand": demand,
                    "priority": priorities[i % 3],
                })

            # 5. Vehículos
            vehicles = []
            for k in range(num_vehicles):
                r, c = _random_free_pos(grid, rows, cols, taken)
                taken.add((r, c))
                all_important_points.append((r, c))
                vehicles.append({
                    "id": f"V{k}",
                    "pos": [r, c],
                    "capacity": vehicle_capacity,
                    "cost_per_step": vehicle_cost,
                })

            # 6. VERIFICAR CONECTIVIDAD
            if is_connected(grid, rows, cols, all_important_points):
                # Si está conectado, ajustamos inventario y terminamos
                for d in depots:
                    required_stock = sum(c["demand"].get(d["id"], 0) for c in clients)
                    if required_stock > d["inventory"]:
                        d["inventory"] = required_stock + 5
                    elif required_stock == 0:
                        d["inventory"] = max(5, d["inventory"])

                return {
                    "scenario_name": scenario_name,
                    "seed": seed,
                    "grid": {
                        "rows": rows, "cols": cols,
                        "traffic_penalty": traffic_penalty,
                        "cells": grid,
                    },
                    "depots": depots, "clients": clients, "vehicles": vehicles,
                }
            else:
                # Reintento con otra semilla interna si falla conectividad
                random.seed(seed + attempt + 1)
                continue

        except RuntimeError:
            # Si no hay espacio, reintenta
            random.seed(seed + attempt + 1)
            continue

    raise RuntimeError("No se pudo generar un mapa conectado tras 100 intentos. Baja los obstáculos.")


# ------------------------------------------------------------------
# Modo interactivo
# ------------------------------------------------------------------

def interactive_generate() -> dict:
    def ask_int(prompt: str, default: int) -> int:
        val = input(f"{prompt} [{default}]: ").strip()
        return int(val) if val else default

    def ask_float(prompt: str, default: float) -> float:
        val = input(f"{prompt} [{default}]: ").strip()
        return float(val) if val else default

    def ask_str(prompt: str, default: str) -> str:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default

    print("\n=== Generador de Escenarios — Modo Interactivo ===\n")
    name = ask_str("Nombre del escenario", "mi_escenario")
    rows = ask_int("Filas del grid (N)", 10)
    cols = ask_int("Columnas del grid (M)", 10)
    n_depots = ask_int("Número de depósitos", 2)
    n_clients = ask_int("Número de clientes", 3)
    n_vehicles = ask_int("Número de vehículos", 2)
    n_obstacles = ask_int("Número de obstáculos", 5)
    n_traffic = ask_int("Número de zonas de tráfico", 3)
    traffic_penalty = ask_float("Penalización de tráfico (multiplicador)", 2.0)
    depot_inv = ask_int("Inventario por depósito (unidades)", 30)
    cli_demand = ask_int("Demanda máxima por cliente/depósito", 10)
    veh_cap = ask_int("Capacidad de cada vehículo", 15)
    veh_cost = ask_float("Coste por paso de cada vehículo", 1.0)
    seed = ask_int("Semilla aleatoria (para reproducibilidad)", 42)

    return generate_scenario(
        rows=rows, cols=cols,
        num_depots=n_depots, num_clients=n_clients, num_vehicles=n_vehicles,
        num_obstacles=n_obstacles, num_traffic=n_traffic,
        depot_inventory=depot_inv, client_demand=cli_demand,
        vehicle_capacity=veh_cap, vehicle_cost=veh_cost,
        traffic_penalty=traffic_penalty,
        scenario_name=name, seed=seed,
    )


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generador de entornos de simulación logística."
    )
    p.add_argument("--output", "-o", default="config/scenario.json",
                   help="Ruta del JSON de salida (default: config/scenario.json)")
    p.add_argument("--interactive", "-i", action="store_true",
                   help="Modo interactivo (pide valores por consola)")
    p.add_argument("--name", default="escenario",
                   help="Nombre del escenario")
    p.add_argument("--rows", type=int, default=10)
    p.add_argument("--cols", type=int, default=10)
    p.add_argument("--depots", type=int, default=2)
    p.add_argument("--clients", type=int, default=3)
    p.add_argument("--vehicles", type=int, default=2)
    p.add_argument("--obstacles", type=int, default=5)
    p.add_argument("--traffic", type=int, default=3)
    p.add_argument("--traffic-penalty", type=float, default=2.0)
    p.add_argument("--depot-inventory", type=int, default=30)
    p.add_argument("--client-demand", type=int, default=10)
    p.add_argument("--vehicle-capacity", type=int, default=15)
    p.add_argument("--vehicle-cost", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=42)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.interactive:
        scenario = interactive_generate()
    else:
        scenario = generate_scenario(
            rows=args.rows, cols=args.cols,
            num_depots=args.depots, num_clients=args.clients,
            num_vehicles=args.vehicles,
            num_obstacles=args.obstacles, num_traffic=args.traffic,
            depot_inventory=args.depot_inventory,
            client_demand=args.client_demand,
            vehicle_capacity=args.vehicle_capacity,
            vehicle_cost=args.vehicle_cost,
            traffic_penalty=args.traffic_penalty,
            scenario_name=args.name, seed=args.seed,
        )

    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)

    print(f"[Generator] Escenario guardado en: {args.output}")
    print(f"  Grid: {scenario['grid']['rows']}x{scenario['grid']['cols']}")
    print(f"  Depósitos: {len(scenario['depots'])}")
    print(f"  Clientes:  {len(scenario['clients'])}")
    print(f"  Vehículos: {len(scenario['vehicles'])}")
    print(f"  Semilla:   {scenario['seed']}")


if __name__ == "__main__":
    main()
