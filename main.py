"""
main.py — CLI principal del sistema multiagente de logística (v0.4 Actor Model).

Comandos:
  generate   Genera un entorno de simulación y lo guarda en JSON
  simulate   Ejecuta una simulación asíncrona sobre un entorno JSON existente
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import asyncio


def cmd_generate(args) -> None:
    """Subcomando: generar entorno."""
    from tools.env_generator import main as gen_main
    argv = ["--output", args.output]
    if args.interactive:
        argv.append("--interactive")
    else:
        argv += [
            "--name", args.name,
            "--rows", str(args.rows),
            "--cols", str(args.cols),
            "--depots", str(args.depots),
            "--clients", str(args.clients),
            "--vehicles", str(args.vehicles),
            "--obstacles", str(args.obstacles),
            "--traffic", str(args.traffic),
            "--traffic-penalty", str(args.traffic_penalty),
            "--depot-inventory", str(args.depot_inventory),
            "--client-demand", str(args.client_demand),
            "--vehicle-capacity", str(args.vehicle_capacity),
            "--vehicle-cost", str(args.vehicle_cost),
            "--seed", str(args.seed),
        ]
    gen_main(argv)


async def cmd_simulate(args) -> None:
    """Subcomando: ejecutar simulación asíncrona (AutoGen v0.4)."""
    if not os.path.isfile(args.scenario):
        print(f"[ERROR] Fichero de escenario no encontrado: {args.scenario}")
        sys.exit(1)

    mode = args.mode.lower()
    verbose = args.verbose

    if mode == "simple":
        from scenarios.simple_scenario import SimpleScenario
        scenario = SimpleScenario.from_json(args.scenario)

    elif mode == "coordinated":
        from scenarios.coordinated_scenario import CoordinatedScenario
        scenario = CoordinatedScenario.from_json(args.scenario)

    elif mode == "rl":
        from scenarios.rl_scenario import RLScenario
        scenario = RLScenario.from_json(
            args.scenario,
            epsilon=args.epsilon,
            alpha=args.alpha,
            gamma=args.gamma,
        )
        if args.episodes > 0:
            await scenario.pretrain(args.episodes, args.scenario, verbose=verbose)

    else:
        print(f"[ERROR] Modo desconocido: {mode}. Use: simple | coordinated | rl")
        sys.exit(1)

    # Preparar visualizador si verbose
    viz = None
    if verbose:
        from simulation.visualizer import Visualizer
        viz = Visualizer()
    
    # Ejecutar motor asíncrono
    metrics = await scenario.run(verbose=verbose, visualizer=viz)

    # Mostrar resumen
    metrics.print_summary()

    # Guardar resultado JSON (Automático si no se especifica --output)
    output_path = args.output
    if not output_path:
        # Generar nombre automático: results/res_<escenario>_<modo>.json
        scenario_base = os.path.splitext(os.path.basename(args.scenario))[0]
        output_path = f"results/res_{scenario_base}_{mode}.json"

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        result = metrics.to_dict()
        if mode == "rl":
            result["rl_stats"] = scenario.get_rl_stats()
        if mode == "coordinated":
            result["assignment_log"] = scenario.get_assignment_log()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[Simulate] Resultado guardado en: {output_path}")


def main():
    parser = build_main_parser()
    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "simulate":
        # Arrancar el bucle de eventos asíncronos para AutoGen v0.4
        asyncio.run(cmd_simulate(args))


def build_main_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logistics_mas",
        description="Sistema Multiagente de Logística — CLI (v0.4 Actor Model)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── generate ────────────────────────────────────────────────────
    gen = sub.add_parser("generate", help="Generar entorno de simulación JSON")
    gen.add_argument("--output", "-o", default="config/scenario.json")
    gen.add_argument("--interactive", "-i", action="store_true")
    gen.add_argument("--name", default="escenario")
    gen.add_argument("--rows", type=int, default=10)
    gen.add_argument("--cols", type=int, default=10)
    gen.add_argument("--depots", type=int, default=2)
    gen.add_argument("--clients", type=int, default=3)
    gen.add_argument("--vehicles", type=int, default=2)
    gen.add_argument("--obstacles", type=int, default=5)
    gen.add_argument("--traffic", type=int, default=3)
    gen.add_argument("--traffic-penalty", type=float, default=2.0)
    gen.add_argument("--depot-inventory", type=int, default=30)
    gen.add_argument("--client-demand", type=int, default=10)
    gen.add_argument("--vehicle-capacity", type=int, default=15)
    gen.add_argument("--vehicle-cost", type=float, default=1.0)
    gen.add_argument("--seed", type=int, default=42)

    # ── simulate ─────────────────────────────────────────────────────
    sim = sub.add_parser("simulate", help="Ejecutar simulación sobre un JSON")
    sim.add_argument("--scenario", "-s", required=True, help="Ruta al JSON del escenario")
    sim.add_argument("--mode", "-m", default="simple", choices=["simple", "coordinated", "rl"], help="Modo de simulación")
    sim.add_argument("--output", "-o", default=None, help="Ruta para guardar el JSON de resultados")
    sim.add_argument("--verbose", "-v", action="store_true", help="Monitorización en tiempo real")
    sim.add_argument("--episodes", type=int, default=0, help="Episodios pre-entrenamiento (modo rl)")
    sim.add_argument("--epsilon", type=float, default=0.3, help="Exploración ε (modo rl)")
    sim.add_argument("--alpha", type=float, default=0.1, help="Tasa aprendizaje α (modo rl)")
    sim.add_argument("--gamma", type=float, default=0.9, help="Factor descuento γ (modo rl)")

    return parser


if __name__ == "__main__":
    main()
